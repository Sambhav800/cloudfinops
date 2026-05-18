import { createClient } from "@/lib/mongodb/client";
import { GeminiAIClient, AnalysisResult } from "./gemini";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

const formatAiImpactInr = (value: number) =>
    formatInrCurrency(toDisplayInrAmount(value, "USD"), { maximumFractionDigits: 0 });

/**
 * Orchestrates the AI FinOps Pipeline
 * Scanner -> Metadata -> Gemini AI -> Insights -> Database
 */
export async function runAiPipeline(userId: string, integrationId: string) {
    console.log(`[AI Pipeline] Starting analysis for integration ${integrationId}...`);

    // Initialize MongoDB Admin
    const db = createClient(process.env.MONGODB_URI);

    // 1. Fetch Integration & Resources
    const { data: resources, error } = await db
        .from('resources')
        .select('*')
        .eq('user_id', userId)
        // Note: Ideally filter by integration_id too if resources table has it, 
        // but currently scanning refreshes all user resources or we filter strictly here.
        // For now, let's analyze ALL user resources to give holistic advice.
        .limit(100); // Limit context window for now

    if (error || !resources || resources.length === 0) {
        console.log("[AI Pipeline] No resources found to analyze.");
        return;
    }

    // 2. Call Gemini AI
    const gemini = new GeminiAIClient();
    const result: AnalysisResult = await gemini.analyzeInfrastructure(resources);

    // 3. Store Results in Database

    // A. Store Governance Score / Summary
    /* 
       We might want a dedicated 'analysis_runs' table, but for now 
       we use 'agent_notifications' to alert the user.
    */

    // Create a summary notification (always generate one so user sees AI analyzed their infra)
    const highSeverity = result.findings.filter(f => f.severity === 'high').length;
    const issueCount = result.findings.length;

    // Delete old AI insight notifications for this user (prevent duplicates)
    await db.from('agent_notifications').delete()
        .eq('user_id', userId)
        .eq('type', 'ai_insight');

    await db.from('agent_notifications').insert({
        user_id: userId,
        type: 'ai_insight',
        status: 'pending', // Pending user review
        action: 'review',
        resource_id: null, // System-level insight, no specific resource UUID
        recommendation: issueCount > 0
            ? `AI Analysis Complete: Found ${issueCount} issues (${highSeverity} High Severity)`
            : `AI Analysis Complete: Infrastructure looks healthy! Score: ${result.governance_score}/100`,
        metadata: {
            analysis_id: result.analysis_id,
            score: result.governance_score,
            findings: result.findings,
            summary: result.summary,
            // Fix for "Unknown" type bug - derive from findings
            resource_type: result.findings[0]?.resource_id?.includes('VM') ? 'Azure VM' :
                result.findings[0]?.resource_id?.includes('Disk') ? 'Azure Disk' :
                    result.findings[0]?.resource_id?.includes('IP') ? 'Azure Public IP' :
                        'Infrastructure',
            risk_level: highSeverity > 0 ? 'high' : issueCount > 0 ? 'medium' : 'low',
            estimated_savings: result.findings.reduce((sum, f) => sum + (f.potential_savings || 0), 0),
            description: result.summary
        }
    });

    // B. Store Ghost Resources (Zombies)
    // Map 'cost' warnings to potential ghost resources
    const zombieFindings = result.findings.filter(f => f.category === 'cost' && f.issue.includes('Unused'));

    if (zombieFindings.length > 0) {
        console.log(`[AI Pipeline] AI identified ${zombieFindings.length} complex zombie resources.`);
    }

    // C. Create/Update Governance Policies based on AI findings
    // This populates the Governance page
    const policyTypes = ['tagging', 'cost', 'security', 'utilization'];
    const policiesFromAI = result.findings.map((f, _idx) => ({
        user_id: userId,
        name: f.issue,
        description: f.recommendation,
        policy_type: policyTypes.find(p => f.category?.includes(p)) || 'cost',
        is_active: true,
        metadata: {
            category: f.category || 'cost',
            status: 'fail', // AI findings are issues, so they fail
            severity: f.severity || 'medium',
            reason: f.issue,
            impact: formatAiImpactInr(f.potential_savings || 0),
            compliance_mapping: 'AI FinOps Analysis'
        }
    }));

    // Add a "healthy" policy if no issues found
    if (policiesFromAI.length === 0) {
        policiesFromAI.push({
            user_id: userId,
            name: 'Overall Infrastructure Health',
            description: 'AI Analysis found no critical issues',
            policy_type: 'cost',
            is_active: true,
            metadata: {
                category: 'cost',
                status: 'pass',
                severity: 'low',
                reason: 'No critical issues detected by AI',
                impact: formatInrCurrency(0, { maximumFractionDigits: 0 }),
                compliance_mapping: 'AI FinOps Analysis'
            }
        });
    }

    // Clear old policies and insert fresh
    await db.from('governance_policies').delete().eq('user_id', userId);
    await db.from('governance_policies').insert(policiesFromAI);

    console.log(`[AI Pipeline] Analysis ${result.analysis_id} complete. Score: ${result.governance_score}, Policies: ${policiesFromAI.length}`);
    return result;
}
