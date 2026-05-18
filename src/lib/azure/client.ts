import { ClientSecretCredential } from "@azure/identity";
import { ComputeManagementClient } from "@azure/arm-compute";

/**
 * Azure Credential Options for validation
 */
export type AzureCredentialOptions = {
    tenantId: string;
    clientId: string;
    clientSecret: string;
    subscriptionId: string;
};

/**
 * Validates Azure credentials by attempting to list VMs
 */
export async function validateAzureCredentials(options: AzureCredentialOptions) {
    try {
        const credential = new ClientSecretCredential(
            options.tenantId,
            options.clientId,
            options.clientSecret
        );

        // Try to create a client and make a simple API call
        const computeClient = new ComputeManagementClient(credential, options.subscriptionId);

        // Just get the first page of VMs to verify credentials work
        const vms = computeClient.virtualMachines.listAll();

        // Try to iterate once to validate the connection
        for await (const _vm of vms) {
            // Just need to verify we can access - break after first
            break;
        }

        return {
            valid: true,
            subscriptionId: options.subscriptionId,
            tenantId: options.tenantId
        };

    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Failed to validate Azure credentials";
        console.error("Azure Validation Error:", error);
        return {
            valid: false,
            error: message
        };
    }
}
