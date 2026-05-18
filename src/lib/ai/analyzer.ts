import { GoogleGenerativeAI } from '@google/generative-ai';
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";


// Initialize Gemini AI client (server-side only — never use NEXT_PUBLIC_ for API keys)
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');

interface ScannedResource {
    name: string;
    type: string;
    region: string;
    status: string;
    metadata: Record<string, unknown>;
    provider?: string;
}

// Output interface for the caller
export interface AIAnalysisResult {
    resources: ScannedResource[];
    notifications: AINotification[];
    stats: {
        savings: number;
        carbon: number;
        confidenceScore?: number;
    },
    inventory?: {
        zombieAssets: Record<string, unknown>[];
        orphanedStorage: Record<string, unknown>[];
        shadowIT: Record<string, unknown>[];
        insightSummary: Record<string, unknown> | null;
    }
}

interface AINotification {
    type: string;
    resource_name: string;
    recommendation: string;
    potential_savings: number;
    severity: string;
}

interface RemediationResult {
    plan: { finding: string; steps: string[]; priority: string; estimated_time: string }[];
}

interface ExecutiveReportResult {
    report: string;
    keyMetrics?: { costGrade: string; securityGrade: string; complianceGrade: string };
    actionItems?: string[];
}

interface GovernanceResult {
    policies: { name: string; status: string; description: string; affectedResources: string[]; recommendation: string }[];
    score: number;
    riskLevel?: string;
    complianceFrameworks?: Record<string, number>;
}

interface AnomalyResult {
    anomalies: { type: string; resourceId: string; description: string; severity: string; recommendation: string }[];
    riskScore?: number;
}

interface ContextResource {
    name?: string;
    type?: string;
    status?: string;
    cost?: number;
    region?: string;
    waste?: string;
}

interface ContextAggregate {
    count?: number;
    cost?: number;
}

// Interfaces for the Gemini FinOps Prompt
interface FinOpsInput {
    allowedRegions: string[];
    cloudTrailEvents: Record<string, unknown>[]; // Mocked for now
    ec2Instances: Array<{
        instanceId: string;
        region: string;
        avgCPU7Days: number;
        avgNetworkMB7Days: number;
        monthlyCostINR: number;
    }>;
    ebsVolumes: Array<{
        volumeId: string;
        region: string;
        state: string;
        attachedTo: string | null;
        sizeGB: number;
        monthlyCostINR: number;
    }>;
    snapshots: Array<{
        snapshotId: string;
        region: string;
        ageInDays: number;
        sizeGB: number;
        monthlyCostINR: number;
    }>;
    elasticIPs: Array<{
        allocationId: string;
        region: string;
        associatedInstanceId: string | null;
        monthlyCostINR: number;
    }>;
}

interface FinOpsOutput {
    staleEbsVolumes: { volumeId: string; reason: string; savingsINR: number }[];
    idleEc2Instances: { instanceId: string; avgCPU: number; avgNetwork: string; recommendation: string; savingsINR: number }[];
    oldSnapshots: { snapshotId: string; ageInDays: number; savingsINR: number }[];
    unusedElasticIPs: { allocationId: string; reason: string; savingsINR: number }[];
    credentialsNotRotated: { userName: string; daysOld: number }[];
    resourcesOutsideAllowedRegions: { resourceType: string; resourceId: string; region: string }[];
    rootAccountUsage: { eventCount: number; lastEventTime: string; concern: string }[];
    summary: {
        totalSavingsINR: number;
        criticalCount: number;
        warningCount: number;
    };
}

const FLASH_MODEL = process.env.GEMINI_VERIFY_MODEL || 'gemini-3-flash-preview';
const STRATEGIC_MODEL = process.env.GEMINI_PROPOSE_MODEL || 'gemini-3-flash-preview';
const getStrategicModel = () => genAI.getGenerativeModel({ model: STRATEGIC_MODEL });
const getFlashModel = () => genAI.getGenerativeModel({ model: FLASH_MODEL });

function formatPromptInr(value: unknown): string {
    return formatInrCurrency(Number(value || 0), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function resourceSourceCurrency(resource: ScannedResource): "INR" | "USD" {
    const metadataCurrency = resource.metadata?.currency;
    if (metadataCurrency === "INR" || metadataCurrency === "USD") {
        return metadataCurrency;
    }

    const metadataProvider = resource.metadata?.provider;
    const provider = typeof resource.provider === "string" ? resource.provider.toLowerCase() : "";
    if (metadataProvider === "gcp" || provider === "gcp") {
        return "INR";
    }

    return "USD";
}

function resourceMonthlyCostInInr(resource: ScannedResource): number {
    const rawCost = Number(resource.metadata?.cost ?? 0);
    return toDisplayInrAmount(rawCost, resourceSourceCurrency(resource));
}

/**
 * Main Analysis Function - Uses Gemini 3 Flash for deeper analysis
 */
export async function analyzeInfrastructure(resources: ScannedResource[]): Promise<AIAnalysisResult> {
    if (!process.env.GEMINI_API_KEY) {
        console.warn("Skipping AI analysis: Missing GEMINI_API_KEY");
        return getEmptyResult();
    }

    // Build input for the AI
    const finOpsInput = buildFinOpsInput(resources);

    const systemPrompt = `
You are an enterprise-grade Cloud Governance and FinOps AI powered by Google Gemini.
Your task: Analyze the provided cloud resource JSON. Identify cost waste, security risks, and governance violations.

INPUT SCHEMA:
{
  "allowedRegions": string[],
  "cloudTrailEvents": any[],
  "ec2Instances": [{ instanceId, region, avgCPU7Days, avgNetworkMB7Days, monthlyCostINR }],
  "ebsVolumes": [{ volumeId, region, state, attachedTo, sizeGB, monthlyCostINR }],
  "snapshots": [{ snapshotId, region, ageInDays, sizeGB, monthlyCostINR }],
  "elasticIPs": [{ allocationId, region, associatedInstanceId, monthlyCostINR }]
}

OUTPUT SCHEMA (JSON only):
{
  "staleEbsVolumes": [{ volumeId, reason, savingsINR }],
  "idleEc2Instances": [{ instanceId, avgCPU, avgNetwork, recommendation, savingsINR }],
  "oldSnapshots": [{ snapshotId, ageInDays, savingsINR }],
  "unusedElasticIPs": [{ allocationId, reason, savingsINR }],
  "credentialsNotRotated": [{ userName, daysOld }],
  "resourcesOutsideAllowedRegions": [{ resourceType, resourceId, region }],
  "rootAccountUsage": [{ eventCount, lastEventTime, concern }],
  "summary": { totalSavingsINR, criticalCount, warningCount }
}
Return ONLY valid JSON.
    `.trim();

    try {
        const model = getStrategicModel();
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: `${systemPrompt}\n\nInput:\n${JSON.stringify(finOpsInput)}` }] }],
            generationConfig: {
                temperature: 0.2,
                maxOutputTokens: 4096,
                responseMimeType: "application/json"
            }
        });

        const content = result.response.text();
        const aiOutput: FinOpsOutput = JSON.parse(content);
        return transformToAnalysisResult(resources, aiOutput);

    } catch (error) {
        console.error("Gemini AI analysis error:", error);
        return getEmptyResult();
    }
}

/**
 * Generate Remediation Plans - Uses Flash model for speed
 */
export async function generateRemediationPlan(findings: ScannedResource[]): Promise<RemediationResult> {
    if (!process.env.GEMINI_API_KEY) {
        console.warn("Skipping Remediation: Missing GEMINI_API_KEY");
        return { plan: [] };
    }

    const systemPrompt = `
You are an enterprise DevOps assistant AI powered by Google Gemini.
Generate a structured remediation plan for the following cloud governance findings.
Return JSON: { "plan": [{ "finding": string, "steps": string[], "priority": "high"|"medium"|"low", "estimated_time": string }] }
    `.trim();

    try {
        const model = getFlashModel();
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: `${systemPrompt}\n\nFindings:\n${JSON.stringify(findings)}` }] }],
            generationConfig: {
                temperature: 0.3,
                maxOutputTokens: 2048,
                responseMimeType: "application/json"
            }
        });
        return JSON.parse(result.response.text());
    } catch (error) {
        console.error("Remediation generation error:", error);
        return { plan: [] };
    }
}

/**
 * Generate Executive Report - Uses Gemini 3 Flash
 */
export async function generateExecutiveReport(stats: Record<string, unknown>): Promise<ExecutiveReportResult> {
    if (!process.env.GEMINI_API_KEY) {
        console.warn("Skipping Executive Report: Missing GEMINI_API_KEY");
        return { report: "" };
    }

    const systemPrompt = `
You are an enterprise audit-reporting AI powered by Google Gemini.
Generate a concise executive summary for the following infrastructure stats.
Return JSON: { "report": "markdown formatted report", "keyMetrics": { "costGrade": "A-F", "securityGrade": "A-F", "complianceGrade": "A-F" }, "actionItems": string[] }
    `.trim();

    try {
        const model = getStrategicModel();
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: `${systemPrompt}\n\nStats:\n${JSON.stringify(stats)}` }] }],
            generationConfig: {
                temperature: 0.4,
                maxOutputTokens: 2048,
                responseMimeType: "application/json"
            }
        });
        return JSON.parse(result.response.text());
    } catch (error) {
        console.error("Executive report generation error:", error);
        return { report: "" };
    }
}

/**
 * Governance Deep Analysis - Uses Gemini 3 Flash
 */
export async function analyzeGovernance(resources: ScannedResource[]): Promise<GovernanceResult> {
    if (!process.env.GEMINI_API_KEY) {
        console.warn("Skipping Governance Analysis: Missing GEMINI_API_KEY");
        return { policies: [], score: 0 };
    }

    const systemPrompt = `
You are an enterprise Cloud Governance AI powered by Google Gemini.
Analyze the following resources for compliance with cloud governance best practices.
Return JSON: {
  "policies": [{ "name": string, "status": "pass"|"fail"|"warning", "description": string, "affectedResources": string[], "recommendation": string }],
  "score": number (0-100),
  "riskLevel": "low"|"medium"|"high"|"critical",
  "complianceFrameworks": { "SOC2": number, "ISO27001": number, "GDPR": number }
}
    `.trim();

    try {
        const model = getStrategicModel();
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: `${systemPrompt}\n\nResources:\n${JSON.stringify(resources.slice(0, 50))}` }] }],
            generationConfig: {
                temperature: 0.2,
                maxOutputTokens: 4096,
                responseMimeType: "application/json"
            }
        });
        return JSON.parse(result.response.text());
    } catch (error) {
        console.error("Governance analysis error:", error);
        return { policies: [], score: 0 };
    }
}

/**
 * Anomaly Detection - Uses Flash model for speed
 */
export async function detectAnomalies(resources: ScannedResource[]): Promise<AnomalyResult> {
    if (!process.env.GEMINI_API_KEY) {
        console.warn("Skipping Anomaly Detection: Missing GEMINI_API_KEY");
        return { anomalies: [] };
    }

    const systemPrompt = `
You are a cloud anomaly detection AI powered by Google Gemini.
Analyze resources for unusual patterns, potential threats, or cost anomalies.
Return JSON: {
  "anomalies": [{ "type": "security"|"cost"|"performance", "resourceId": string, "description": string, "severity": "low"|"medium"|"high"|"critical", "recommendation": string }],
  "riskScore": number (0-100)
}
    `.trim();

    try {
        const model = getFlashModel();
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: `${systemPrompt}\n\nResources:\n${JSON.stringify(resources.slice(0, 30))}` }] }],
            generationConfig: {
                temperature: 0.3,
                maxOutputTokens: 2048,
                responseMimeType: "application/json"
            }
        });
        return JSON.parse(result.response.text());
    } catch (error) {
        console.error("Anomaly detection error:", error);
        return { anomalies: [] };
    }
}

/**
 * Clousy Chat Interface - Uses Flash model for responsive chat
 * Now receives live DB context from watchdog.ts server action
 */
export async function askClousy(question: string, context: Record<string, unknown>): Promise<string> {
    if (!process.env.GEMINI_API_KEY) {
        return "I'm currently offline. Please configure the Gemini API key to enable AI features.";
    }

    const totalResources = context.totalResources || 0;
    const totalSpend = context.totalMonthlySpend || 0;
    const zombieCount = context.zombieCount || 0;
    const activeCount = context.activeCount || 0;
    const providers = Array.isArray(context.providers) ? (context.providers as string[]) : [];
    const byType = (context.byType as Record<string, ContextAggregate>) || {};
    const byRegion = (context.byRegion as Record<string, ContextAggregate>) || {};
    const resources = (context.resources as ContextResource[]) || [];
    const zombieResources = (context.zombieResources as ContextResource[]) || [];

    const resourceLines = resources.slice(0, 50).map((r: ContextResource) =>
        `- ${r.name || 'Unknown'} | ${r.type || 'Unknown'} | ${r.status || 'Unknown'} | ${formatPromptInr(r.cost)}/mo | ${r.region || 'unknown'}${r.waste ? ` | waste: ${r.waste}` : ''}`
    ).join('\n');

    const typeLines = Object.entries(byType).map(
        ([type, d]) => `- ${type}: ${Number(d.count || 0)} resources, ${formatPromptInr(d.cost)}/mo`
    ).join('\n');

    const regionLines = Object.entries(byRegion).map(
        ([region, d]) => `- ${region}: ${Number(d.count || 0)} resources, ${formatPromptInr(d.cost)}/mo`
    ).join('\n');

    const zombieLines = zombieResources.map((r: ContextResource) =>
        `- ${r.name || 'Unknown'} (${r.type || 'Unknown'}) -- ${r.status || 'Unknown'}, ${formatPromptInr(r.cost)}/mo`
    ).join('\n');

    const systemPrompt = `You are Clousy, the CloudFinOps AI Assistant.

## LIVE DATA
- Total: ${totalResources} resources | ${formatPromptInr(totalSpend)}/mo
- Active: ${activeCount} | Zombie/waste: ${zombieCount}
- Providers: ${providers.join(', ') || 'None'}

### By Type
${typeLines || 'No data'}

### By Region
${regionLines || 'No data'}

### Resources
${resourceLines || 'None'}

${zombieResources.length > 0 ? '### Zombies\n' + zombieLines : ''}

## RULES
1. Answer ONLY from the data above. Never invent numbers.
2. Use markdown tables when listing resources.
3. Be specific in recommendations (e.g. "Delete zombie-forgotten-vm to save ₹1,439.22/mo").
4. Keep responses concise.`;

    try {
        const model = getFlashModel();
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: systemPrompt + '\n\nUser: ' + question }] }],
            generationConfig: {
                temperature: 0.3,
                maxOutputTokens: 2048
            }
        });
        return result.response.text();
    } catch (error) {
        console.error("Clousy chat error:", error);
        return "I encountered an error. Please try again.";
    }
}

// --- Helper Functions ---

function buildFinOpsInput(resources: ScannedResource[]): FinOpsInput {
    return {
        allowedRegions: ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-south-1'],
        cloudTrailEvents: [],
        ec2Instances: resources
            .filter(r => r.type?.includes('EC2') || r.type?.includes('VM'))
            .map(r => ({
                instanceId: r.name,
                region: r.region || 'unknown',
                avgCPU7Days: Number((r.metadata?.cpu_utilization as number) ?? 0),
                avgNetworkMB7Days: Number((r.metadata?.network_mb as number) ?? 0),
                monthlyCostINR: resourceMonthlyCostInInr(r)
            })),
        ebsVolumes: resources
            .filter(r => r.type?.includes('Volume') || r.type?.includes('Disk'))
            .map(r => ({
                volumeId: r.name,
                region: r.region || 'unknown',
                state: r.status || 'available',
                attachedTo: (r.metadata?.attached_to as string) || null,
                sizeGB: (r.metadata?.size_gb as number) || 100,
                monthlyCostINR: resourceMonthlyCostInInr(r)
            })),
        snapshots: resources
            .filter(r => r.type?.includes('Snapshot'))
            .map(r => ({
                snapshotId: r.name,
                region: r.region || 'unknown',
                ageInDays: (r.metadata?.age_days as number) || 30,
                sizeGB: (r.metadata?.size_gb as number) || 50,
                monthlyCostINR: resourceMonthlyCostInInr(r)
            })),
        elasticIPs: resources
            .filter(r => r.type?.includes('IP') || r.type?.includes('Elastic'))
            .map(r => ({
                allocationId: r.name,
                region: r.region || 'unknown',
                associatedInstanceId: (r.metadata?.associated_instance as string) || null,
                monthlyCostINR: resourceMonthlyCostInInr(r)
            }))
    };
}

function transformToAnalysisResult(resources: ScannedResource[], aiOutput: FinOpsOutput): AIAnalysisResult {
    const notifications: AINotification[] = [];

    // Transform AI findings into notifications
    aiOutput.staleEbsVolumes?.forEach(v => {
        notifications.push({
            type: 'cost_optimization',
            resource_name: v.volumeId,
            recommendation: v.reason,
            potential_savings: v.savingsINR / 83,
            severity: 'medium'
        });
    });

    aiOutput.idleEc2Instances?.forEach(i => {
        notifications.push({
            type: 'cost_optimization',
            resource_name: i.instanceId,
            recommendation: i.recommendation,
            potential_savings: i.savingsINR / 83,
            severity: 'high'
        });
    });

    return {
        resources,
        notifications,
        stats: {
            savings: aiOutput.summary?.totalSavingsINR / 83 || 0,
            carbon: notifications.length * 10,
            confidenceScore: 85
        },
        inventory: {
            zombieAssets: aiOutput.idleEc2Instances || [],
            orphanedStorage: aiOutput.staleEbsVolumes || [],
            shadowIT: aiOutput.resourcesOutsideAllowedRegions || [],
            insightSummary: aiOutput.summary
        }
    };
}

function getEmptyResult(): AIAnalysisResult {
    return {
        resources: [],
        notifications: [],
        stats: { savings: 0, carbon: 0, confidenceScore: 0 },
        inventory: { zombieAssets: [], orphanedStorage: [], shadowIT: [], insightSummary: null }
    };
}
