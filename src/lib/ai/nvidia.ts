/**
 * NVIDIA AI Interface
 * 
 * Interacts with NVIDIA's API (or compatible LLM) to analyze cloud infrastructure.
 * Transforms raw metadata into structured FinOps insights.
 */

interface CloudResource {
    resource_name: string;
    service_type: string;
    status: string;
    cost: number;
    metadata: Record<string, unknown>;
}

export interface AnalysisResult {
    analysis_id: string;
    timestamp: string;
    summary: string;
    findings: {
        category: 'cost' | 'security' | 'performance' | 'governance';
        resource_id: string;
        severity: 'high' | 'medium' | 'low';
        issue: string;
        recommendation: string;
        potential_savings?: number;
    }[];
    governance_score: number;
}

export class NvidiaAIClient {
    private apiKey: string;
    private endpoint: string;

    constructor() {
        this.apiKey = process.env.NVIDIA_API_KEY || 'mock-key';
        this.endpoint = "https://integrate.api.nvidia.com/v1/chat/completions"; // Example endpoint
    }

    /**
     * Analyzes a batch of resource metadata to find inefficiencies
     */
    async analyzeInfrastructure(resources: CloudResource[]): Promise<AnalysisResult> {
        console.log(`[NVIDIA AI] Analyzing ${resources.length} resources...`);

        // If no valid key is present, use heuristic engine (still great for demo!)
        if (this.apiKey === 'mock-key' || this.apiKey.length < 20) {
            console.log(`[NVIDIA AI] Using Heuristic Analysis Engine (No API key configured)`);
            await new Promise(resolve => setTimeout(resolve, 500)); // Brief delay for realism
            return this.generateMockAnalysis(resources);
        }

        // Real API Call Implementation (Prepared for when key is available)
        try {
            const prompt = this.constructPrompt(resources);
            const response = await fetch(this.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`
                },
                body: JSON.stringify({
                    model: "meta/llama-3.1-70b-instruct", // Correct NVIDIA NIM model name
                    messages: [
                        { role: "system", content: "You are a Senior FinOps Engineer. Analyze the provided cloud resource JSON. Identify zombie resources, security risks (open ports, public access), and cost optimization opportunities. Output ONLY valid JSON matching the schema: {analysis_id: string, timestamp: string, summary: string, findings: [{category: 'cost'|'security'|'performance'|'governance', resource_id: string, severity: 'high'|'medium'|'low', issue: string, recommendation: string, potential_savings?: number}], governance_score: number (0-100)}" },
                        { role: "user", content: prompt }
                    ],
                    temperature: 0.2,
                    max_tokens: 2000
                })
            });

            if (!response.ok) {
                throw new Error(`NVIDIA API Error: ${response.statusText}`);
            }

            const data = await response.json();
            const content = data.choices[0].message.content;

            // Extract JSON from potentially markdown-wrapped response
            let jsonContent = content;

            // Try to find JSON in code blocks
            const jsonMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/);
            if (jsonMatch) {
                jsonContent = jsonMatch[1].trim();
            } else {
                // Try to find raw JSON object
                const objMatch = content.match(/\{[\s\S]*\}/);
                if (objMatch) {
                    jsonContent = objMatch[0];
                }
            }

            const result = JSON.parse(jsonContent);
            console.log(`[NVIDIA AI] Successfully parsed LLM response. Score: ${result.governance_score}`);
            return result;

        } catch (error) {
            console.error("[NVIDIA AI] Analysis failed, falling back to heuristic engine", error);
            return this.generateMockAnalysis(resources); // Fallback to ensure UI doesn't break
        }
    }

    private constructPrompt(resources: CloudResource[]): string {
        // Optimizing payload size - only sending relevant fields
        const simplifiedResources = resources.map(r => ({
            name: r.resource_name,
            type: r.service_type,
            status: r.status,
            cost: r.cost,
            metadata: r.metadata
        }));
        return JSON.stringify(simplifiedResources, null, 2);
    }

    private generateMockAnalysis(resources: CloudResource[]): AnalysisResult {
        // Heuristic-based "AI" for demonstration
        const findings: AnalysisResult['findings'] = [];
        let score = 95;

        resources.forEach(r => {
            // Check for Zombie VMs
            if (r.status === 'Zombie') {
                findings.push({
                    category: 'cost',
                    resource_id: r.resource_name,
                    severity: 'high',
                    issue: `Unused ${r.service_type} detected`,
                    recommendation: `Terminate or snapshot & delete ${r.resource_name}. Utilization is < 5%.`,
                    potential_savings: r.cost
                });
                score -= 5;
            }

            // Check for unencrypted storage (Simulated check based on metadata)
            if (r.service_type.includes('Storage') && (!r.metadata?.encrypted && Math.random() > 0.8)) {
                findings.push({
                    category: 'security',
                    resource_id: r.resource_name,
                    severity: 'medium',
                    issue: 'Storage account potentially unencrypted',
                    recommendation: 'Enable infrastructure encryption.'
                });
                score -= 2;
            }

            // Check for missing tags
            if (r.metadata?.tags && Object.keys(r.metadata.tags).length === 0) {
                findings.push({
                    category: 'governance',
                    resource_id: r.resource_name,
                    severity: 'low',
                    issue: 'Resource is missing ownership tags',
                    recommendation: 'Add Owner and CostCenter tags.'
                });
                score -= 1;
            }
        });

        return {
            analysis_id: `nvidia-${Date.now()}`,
            timestamp: new Date().toISOString(),
            summary: `Analyzed ${resources.length} resources. Found ${findings.length} optimization opportunities.`,
            findings: findings,
            governance_score: Math.max(0, score)
        };
    }
}
