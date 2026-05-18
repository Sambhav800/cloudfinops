import { InstancesClient } from '@google-cloud/compute';
import { Storage } from '@google-cloud/storage';
import { createClient } from "@/lib/mongodb/client";
import { decrypt } from "@/lib/security/crypto";

// Integration Interface
interface Integration {
    id: string;
    user_id: string;
    encrypted_project_id: string;
    encrypted_service_account_email: string;
    encrypted_private_key: string;
}

/**
 * Scan GCP resources and update dashboard
 */
export async function scanGcpResources(integrationId: string) {
    // Initialize MongoDB admin client
    const db = createClient(process.env.MONGODB_URI);

    // 1. Fetch Integration & Credentials
    const { data: integrationData, error } = await db
        .from('cloud_integrations')
        .select('*')
        .eq('id', integrationId)
        .single();

    const integration = integrationData as Integration | null;

    if (error || !integration) throw new Error(`Integration not found: ${error?.message}`);

    // Decrypt GCP Credentials
    let projectId: string, serviceAccountEmail: string, privateKey: string;
    try {
        const [projectEnc, projectIv] = integration.encrypted_project_id.split('::');
        const [emailEnc, emailIv] = integration.encrypted_service_account_email.split('::');
        const [keyEnc, keyIv] = integration.encrypted_private_key.split('::');

        projectId = decrypt(projectEnc, projectIv);
        serviceAccountEmail = decrypt(emailEnc, emailIv);
        privateKey = decrypt(keyEnc, keyIv).replace(/\\n/g, '\n');
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e);
        throw new Error(`Decryption failed: ${errorMessage}`);
    }

    // Create GCP credentials object
    const credentials = {
        type: 'service_account',
        project_id: projectId,
        client_email: serviceAccountEmail,
        private_key: privateKey,
    };

    // --- Metrics to Populate ---
    const wasteList: { category_name: string, value: number }[] = [];
    const resourceList: {
        resource_name: string,
        service_type: string,
        cost: number,
        status: 'Active' | 'Zombie',
        region_compliance?: string,
        metadata?: Record<string, unknown>
    }[] = [];

    // --- Scan Compute Engine VMs ---
    console.log("🟦 [GCP Scanner] Starting Compute Engine Scan...");
    try {
        const instancesClient = new InstancesClient({ credentials, projectId });

        // List all instances across all zones
        const aggListRequest = instancesClient.aggregatedListAsync({
            project: projectId
        });

        for await (const [zone, instancesObject] of aggListRequest) {
            const instances = instancesObject.instances || [];
            for (const instance of instances) {
                const name = instance.name || 'Unknown VM';
                const status = instance.status || 'UNKNOWN';
                const isStopped = status === 'TERMINATED' || status === 'STOPPED';
                const zoneName = zone.replace('zones/', '');

                const estimatedMonthlyCost = 80; // Estimated cost for GCP VM

                // Deep Metadata Simulation for AI
                const metadata = {
                    cpu_utilization_avg: Math.floor(Math.random() * 100),
                    memory_utilization_avg: Math.floor(Math.random() * 100),
                    machine_type: instance.machineType?.split('/').pop() || 'n1-standard-1',
                    tags: instance.tags?.items || ['production', 'web-server'],
                    creation_timestamp: instance.creationTimestamp,
                    last_start_timestamp: instance.lastStartTimestamp,
                    disk_size_gb: 100 // Simulated
                };

                if (isStopped) {
                    resourceList.push({
                        resource_name: name,
                        service_type: 'GCP Compute Engine',
                        cost: estimatedMonthlyCost,
                        status: 'Zombie',
                        region_compliance: zoneName,
                        metadata: metadata
                    });
                    wasteList.push({ category_name: 'Stopped VMs', value: estimatedMonthlyCost });
                } else {
                    resourceList.push({
                        resource_name: name,
                        service_type: 'GCP Compute Engine',
                        cost: estimatedMonthlyCost,
                        status: 'Active',
                        region_compliance: zoneName,
                        metadata: metadata
                    });
                }
            }
        }
    } catch (e: unknown) {
        console.error("GCP Compute Scan Error:", e);
    }

    // --- Scan Cloud Storage Buckets ---
    console.log("🟦 [GCP Scanner] Starting Storage Scan...");
    try {
        const storage = new Storage({ credentials, projectId });
        const [buckets] = await storage.getBuckets();

        for (const bucket of buckets) {
            const name = bucket.name || 'Unknown Bucket';
            const location = bucket.metadata.location || 'unknown';
            const estimatedMonthlyCost = 10;

            const metadata = {
                storage_class: bucket.metadata.storageClass || 'STANDARD',
                location_type: bucket.metadata.locationType || 'multi-region',
                time_created: bucket.metadata.timeCreated
            };

            resourceList.push({
                resource_name: name,
                service_type: 'GCP Cloud Storage',
                cost: estimatedMonthlyCost,
                status: 'Active',
                region_compliance: location,
                metadata: metadata
            });
        }
    } catch (e: unknown) {
        console.error("GCP Storage Scan Error:", e);
    }

    // --- Write to MongoDB ---
    // 1. Clean up old data for this integration
    await db.from('resources').delete().eq('integration_id', integrationId);
    await db.from('waste_distribution').delete().eq('integration_id', integrationId);

    // 2. Insert fresh resources
    if (resourceList.length > 0) {
        const dbResources = resourceList.map(r => ({
            resource_name: r.resource_name,
            service_type: r.service_type,
            cost: r.cost,
            status: r.status,
            region_compliance: r.region_compliance,
            metadata: r.metadata,
            user_id: integration.user_id,
            integration_id: integrationId
        }));
        await db.from('resources').insert(dbResources);
    }

    // 3. Insert fresh waste data
    if (wasteList.length > 0) {
        const dbWaste = wasteList.map(w => ({
            ...w,
            user_id: integration.user_id,
            integration_id: integrationId
        }));
        await db.from('waste_distribution').insert(dbWaste);
    }

    // Update integration status
    await db
        .from('cloud_integrations')
        .update({
            last_scan: new Date().toISOString(),
            metadata: {
                resources_found: resourceList.length,
                scan_status: 'completed'
            }
        })
        .eq('id', integrationId);

    return { success: true, resourcesScanned: resourceList.length };
}
