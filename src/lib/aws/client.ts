import { STSClient, GetCallerIdentityCommand } from "@aws-sdk/client-sts";
import { fromTemporaryCredentials } from "@aws-sdk/credential-providers";

/**
 * Validates the provided credentials by calling GetCallerIdentity.
 * Can be used for IAM Roles (AssumeRole) or static keys.
 */
export type AwsCredentialOptions = {
    type: 'role' | 'keys';
    roleArn?: string;
    externalId?: string;
    accessKeyId?: string;
    secretAccessKey?: string;
    region?: string;
};

export async function validateAwsCredentials(options: AwsCredentialOptions) {
    const region = options.region || 'us-east-1';

    try {
        const clientConfig: Record<string, unknown> = { region };

        if (options.type === 'role' && options.roleArn) {
            // Assume Role Logic
            const roleCredentials = fromTemporaryCredentials({
                params: {
                    RoleArn: options.roleArn,
                    ExternalId: options.externalId,
                    RoleSessionName: 'CloudFinOps-Verification'
                },
                clientConfig: { region }
            });
            clientConfig.credentials = roleCredentials;
        } else if (options.type === 'keys' && options.accessKeyId && options.secretAccessKey) {
            // Static Keys Logic
            clientConfig.credentials = {
                accessKeyId: options.accessKeyId,
                secretAccessKey: options.secretAccessKey
            };
        } else {
            throw new Error("Invalid credential configuration");
        }

        const client = new STSClient(clientConfig);
        const command = new GetCallerIdentityCommand({});
        const response = await client.send(command);

        return {
            valid: true,
            accountId: response.Account,
            arn: response.Arn,
            userId: response.UserId
        };

    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Failed to validate AWS credentials";
        console.error("AWS Validation Error:", error);
        return {
            valid: false,
            error: message
        };
    }
}
