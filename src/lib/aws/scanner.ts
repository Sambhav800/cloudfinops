import { EC2Client, DescribeInstancesCommand, DescribeVolumesCommand, DescribeAddressesCommand } from "@aws-sdk/client-ec2";
import { CostExplorerClient, GetCostAndUsageCommand } from "@aws-sdk/client-cost-explorer";
import { createClient } from "@/lib/mongodb/client";
import { decrypt } from "@/lib/security/crypto";
import { AwsCredentialOptions } from "./client";

// All AWS Regions to scan if user doesn't specify
const ALL_AWS_REGIONS = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1',
    'ap-south-1', 'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
    'ap-southeast-1', 'ap-southeast-2',
    'sa-east-1', // Brazil
    'ca-central-1'
];

// Approved regions (for Shadow IT detection) - customize per org
const APPROVED_REGIONS = ['us-east-1', 'us-west-2', 'eu-west-1'];

// --- Helper: Fetch Daily Spend (Last 7 Days) ---
async function getDailySpend(client: CostExplorerClient) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 6);

    const command = new GetCostAndUsageCommand({
        TimePeriod: {
            Start: startDate.toISOString().split('T')[0],
            End: endDate.toISOString().split('T')[0]
        },
        Granularity: 'DAILY',
        Metrics: ['UnblendedCost']
    });

    try {
        const response = await client.send(command);
        return response.ResultsByTime?.map(r => ({
            date: r.TimePeriod?.Start || '',
            amount: parseFloat(r.Total?.UnblendedCost?.Amount || '0')
        })) || [];
    } catch (e) {
        console.error("Failed to fetch daily spend:", e);
        return [];
    }
}

// --- Helper: Fetch Total Monthly Cost ---
async function getMonthlyCost(client: CostExplorerClient) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(1);

    const command = new GetCostAndUsageCommand({
        TimePeriod: {
            Start: startDate.toISOString().split('T')[0],
            End: endDate.toISOString().split('T')[0]
        },
        Granularity: 'MONTHLY',
        Metrics: ['UnblendedCost']
    });

    try {
        const response = await client.send(command);
        return parseFloat(response.ResultsByTime?.[0]?.Total?.UnblendedCost?.Amount || '0');
    } catch (e) {
        console.error("Failed to fetch monthly cost:", e);
        return 0;
    }
}

// Resource type for storage
interface ScannedResource {
    resource_name: string;
    service_type: string;
    cost: number;
    status: 'Active' | 'Zombie';
    created_by?: string;
    region: string; // Actual AWS region
    region_compliance: 'compliant' | 'shadow_it';
}

// Integration Interface
interface Integration {
    id: string;
    user_id: string;
    encrypted_access_key_id?: string;
    encrypted_secret_access_key?: string;
    encrypted_role_arn?: string;
    encrypted_external_id?: string;
    regions?: string[];
}

// --- Main Scan Function ---
export async function scanResources(integrationId: string) {
    const db = createClient(process.env.MONGODB_URI);

    // 1. Fetch Integration & Credentials
    const { data: integrationData, error } = await db
        .from('cloud_integrations')
        .select('*')
        .eq('id', integrationId)
        .single();

    const integration = integrationData as Integration | null;

    if (error || !integration) throw new Error(`Integration not found: ${error?.message}`);

    // Decrypt Credentials
    let credentials: AwsCredentialOptions;
    try {
        if (integration.encrypted_access_key_id && integration.encrypted_secret_access_key) {
            const [keyEnc, keyIv] = integration.encrypted_access_key_id.split('::');
            const [secEnc, secIv] = integration.encrypted_secret_access_key.split('::');
            credentials = {
                type: 'keys',
                accessKeyId: decrypt(keyEnc, keyIv),
                secretAccessKey: decrypt(secEnc, secIv),
                region: 'us-east-1' // Default for Cost Explorer
            };
        } else if (integration.encrypted_role_arn) {
            const [roleEnc, roleIv] = integration.encrypted_role_arn.split('::');
            const roleArn = decrypt(roleEnc, roleIv);
            let externalId;
            if (integration.encrypted_external_id) {
                const [extEnc, extIv] = integration.encrypted_external_id.split('::');
                externalId = decrypt(extEnc, extIv);
            }
            credentials = {
                type: 'role',
                roleArn,
                externalId,
                region: 'us-east-1'
            };
        } else {
            throw new Error("No valid credentials found");
        }
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e);
        throw new Error(`Decryption failed: ${errorMessage}`);
    }

    const baseCredentials = {
        accessKeyId: credentials.accessKeyId!,
        secretAccessKey: credentials.secretAccessKey!
    };

    // --- Metrics to Populate ---
    let totalSpend = 0;
    let potentialSavings = 0;
    let activeResourcesCount = 0;
    let carbonFootprint = 0;
    const wasteList: { category_name: string, value: number }[] = [];
    const resourceList: ScannedResource[] = [];

    // --- Step 1: Cost Data (Global - uses us-east-1) ---
    const ceClient = new CostExplorerClient({ region: 'us-east-1', credentials: baseCredentials });
    totalSpend = await getMonthlyCost(ceClient);

    // _dailySpendData is unused, but the call might be useful for future. 
    // Commenting out to avoid unused var warning if I don't use it.
    // const _dailySpendData = await getDailySpend(ceClient);

    // --- Step 2: Determine regions to scan ---
    const regionsToScan = integration.regions && integration.regions.length > 0
        ? integration.regions
        : ALL_AWS_REGIONS;

    console.log(`Scanning ${regionsToScan.length} AWS regions:`, regionsToScan);

    // --- Step 3: Scan each region ---
    for (const region of regionsToScan) {
        const ec2Client = new EC2Client({ region, credentials: baseCredentials });

        // --- 3a: EC2 Instances ---
        try {
            const instances = await ec2Client.send(new DescribeInstancesCommand({}));
            instances.Reservations?.forEach(res => {
                res.Instances?.forEach(inst => {
                    const name = inst.Tags?.find(t => t.Key === 'Name')?.Value || inst.InstanceId || 'Unknown EC2';
                    const isStopped = inst.State?.Name === 'stopped';
                    const owner = inst.Tags?.find(t => t.Key === 'Owner')?.Value ||
                        inst.Tags?.find(t => t.Key === 'CreatedBy')?.Value || 'Unknown';
                    const isShadowIT = !APPROVED_REGIONS.includes(region);

                    // Carbon footprint: ~72 kg/month for running instance
                    if (!isStopped) carbonFootprint += 72;

                    const estimatedMonthlyCost = 50; // Default estimate

                    if (isStopped) {
                        potentialSavings += estimatedMonthlyCost;
                        wasteList.push({ category_name: 'Idle EC2', value: estimatedMonthlyCost });
                    } else {
                        activeResourcesCount++;
                    }

                    resourceList.push({
                        resource_name: name,
                        service_type: 'AWS EC2 Instance',
                        cost: estimatedMonthlyCost,
                        status: isStopped ? 'Zombie' : 'Active',
                        created_by: owner,
                        region: region,
                        region_compliance: isShadowIT ? 'shadow_it' : 'compliant'
                    });
                });
            });
        } catch (e) {
            console.error(`EC2 Scan Error in ${region}:`, e);
        }

        // --- 3b: EBS Volumes (Unattached = Zombie) ---
        try {
            const volumes = await ec2Client.send(new DescribeVolumesCommand({}));
            volumes.Volumes?.forEach(vol => {
                const name = vol.Tags?.find(t => t.Key === 'Name')?.Value || vol.VolumeId || 'Unknown EBS';
                const isUnattached = vol.State === 'available'; // 'available' means not attached
                const owner = vol.Tags?.find(t => t.Key === 'Owner')?.Value || 'Unknown';
                const isShadowIT = !APPROVED_REGIONS.includes(region);

                // Cost estimate based on size: ~$0.10/GB/month for gp2
                const sizeGB = vol.Size || 0;
                const estimatedMonthlyCost = Math.round(sizeGB * 0.10);

                if (isUnattached) {
                    potentialSavings += estimatedMonthlyCost;
                    wasteList.push({ category_name: 'Orphaned EBS', value: estimatedMonthlyCost });
                } else {
                    activeResourcesCount++;
                }

                resourceList.push({
                    resource_name: name,
                    service_type: 'AWS EBS Volume',
                    cost: estimatedMonthlyCost,
                    status: isUnattached ? 'Zombie' : 'Active',
                    created_by: owner,
                    region: region,
                    region_compliance: isShadowIT ? 'shadow_it' : 'compliant'
                });
            });
        } catch (e) {
            console.error(`EBS Scan Error in ${region}:`, e);
        }

        // --- 3c: Elastic IPs (Unassociated = Zombie) ---
        try {
            const addresses = await ec2Client.send(new DescribeAddressesCommand({}));
            addresses.Addresses?.forEach(addr => {
                const name = addr.Tags?.find(t => t.Key === 'Name')?.Value || addr.PublicIp || 'Unknown EIP';
                const isUnassociated = !addr.AssociationId; // No association = unused
                const owner = addr.Tags?.find(t => t.Key === 'Owner')?.Value || 'Unknown';
                const isShadowIT = !APPROVED_REGIONS.includes(region);

                // Unused EIPs cost ~$3.60/month
                const estimatedMonthlyCost = isUnassociated ? 4 : 0;

                if (isUnassociated) {
                    potentialSavings += estimatedMonthlyCost;
                    wasteList.push({ category_name: 'Unused Elastic IP', value: estimatedMonthlyCost });
                }

                resourceList.push({
                    resource_name: name,
                    service_type: 'AWS Elastic IP',
                    cost: estimatedMonthlyCost,
                    status: isUnassociated ? 'Zombie' : 'Active',
                    created_by: owner,
                    region: region,
                    region_compliance: isShadowIT ? 'shadow_it' : 'compliant'
                });
            });
        } catch (e) {
            console.error(`Elastic IP Scan Error in ${region}:`, e);
        }
    }

    console.log(`Scan complete: Found ${resourceList.length} resources across ${regionsToScan.length} regions`);

    // Cost of Inaction: 6-month projection
    const costOfInaction = potentialSavings * 6;

    // --- Step 4: Write to MongoDB ---

    // 1. Dashboard Stats
    await db.from('dashboard_stats').delete().eq('integration_id', integrationId);
    await db.from('dashboard_stats').insert({
        user_id: integration.user_id,
        integration_id: integrationId,
        total_spend: totalSpend,
        potential_savings: potentialSavings,
        active_resources_count: activeResourcesCount,
        ai_confidence_score: 85,
        carbon_footprint_kg: carbonFootprint,
        cost_of_inaction_6mo: costOfInaction
    });

    // 2. Waste Distribution
    await db.from('waste_distribution').delete().eq('integration_id', integrationId);
    if (wasteList.length > 0) {
        const enrichedWaste = wasteList.map(w => ({
            ...w,
            user_id: integration.user_id,
            integration_id: integrationId
        }));
        await db.from('waste_distribution').insert(enrichedWaste);
    }

    // 3. Resources
    await db.from('resources').delete().eq('integration_id', integrationId);
    if (resourceList.length > 0) {
        const dbResources = resourceList.map(r => ({
            resource_name: r.resource_name,
            service_type: r.service_type,
            cost: r.cost,
            status: r.status,
            created_by: r.created_by,
            region_compliance: r.region,  // Store actual region here for display
            user_id: integration.user_id,
            integration_id: integrationId,
            metadata: {
                aws_region: r.region,
                is_shadow_it: r.region_compliance === 'shadow_it'
            }
        }));
        await db.from('resources').insert(dbResources);
    }

    // Update integration status
    await db
        .from('cloud_integrations')
        .update({
            last_scan: new Date().toISOString(),
            metadata: {
                last_month_cost: totalSpend,
                scan_status: 'completed',
                regions_scanned: regionsToScan.length,
                resources_found: resourceList.length
            }
        })
        .eq('id', integrationId);

    // 4. Trigger AI Analysis
    if (resourceList.length > 0) {
        try {
            const { analyzeInfrastructure } = await import("@/lib/ai/analyzer");
            const aiResources = resourceList.map(r => ({
                name: r.resource_name,
                type: r.service_type,
                region: r.region,
                status: r.status,
                metadata: { cost: r.cost, is_shadow_it: r.region_compliance === 'shadow_it' }
            }));

            const analysisResult = await analyzeInfrastructure(aiResources);

            if (analysisResult?.stats) {
                const updates: Record<string, number> = {
                    carbon_footprint_kg: analysisResult.stats.carbon || carbonFootprint,
                    potential_savings: analysisResult.stats.savings || potentialSavings
                };
                if (analysisResult.stats.confidenceScore && analysisResult.stats.confidenceScore > 0) {
                    updates.ai_confidence_score = analysisResult.stats.confidenceScore;
                }
                await db.from('dashboard_stats').update(updates).eq('integration_id', integrationId);
            }
        } catch (aiError) {
            console.error("AI Analysis Trigger Failed:", aiError);
        }
    }

    return {
        success: true,
        resourcesFound: resourceList.length,
        regionsScanned: regionsToScan.length,
        potentialSavings
    };
}
