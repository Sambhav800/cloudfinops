import { GoogleAuth } from 'google-auth-library';

/**
 * GCP Credential Options for validation
 */
export type GcpCredentialOptions = {
    projectId: string;
    serviceAccountEmail: string;
    privateKey: string;
};

function extractPrivateKeyFromJson(raw: string): string | null {
    const objectStart = raw.indexOf('{');
    const objectEnd = raw.lastIndexOf('}');
    if (objectStart === -1 || objectEnd <= objectStart) {
        return null;
    }

    const jsonText = raw.slice(objectStart, objectEnd + 1);
    try {
        const parsed = JSON.parse(jsonText) as Record<string, unknown>;
        return typeof parsed.private_key === 'string' ? parsed.private_key : null;
    } catch {
        return null;
    }
}

function extractPrivateKeyFromSnippet(raw: string): string | null {
    const match = raw.match(/["']?private_key["']?\s*:\s*["']([\s\S]*?)["']/i);
    if (!match?.[1]) {
        return null;
    }

    return match[1];
}

function normalizePrivateKey(rawPrivateKey: string): string {
    let privateKey = rawPrivateKey.trim();
    privateKey = extractPrivateKeyFromJson(privateKey)
        ?? extractPrivateKeyFromSnippet(privateKey)
        ?? privateKey;

    privateKey = privateKey
        .replace(/^["']|["']$/g, '')
        .replace(/\r\n/g, '\n')
        .replace(/\\n/g, '\n')
        .trim();

    const beginMarker = '-----BEGIN PRIVATE KEY-----';
    const endMarker = '-----END PRIVATE KEY-----';
    const beginIndex = privateKey.indexOf(beginMarker);
    const endIndex = privateKey.indexOf(endMarker);

    if (beginIndex !== -1 && endIndex > beginIndex) {
        const rawBody = privateKey
            .slice(beginIndex + beginMarker.length, endIndex)
            .replace(/[\r\n\s]/g, '')
            .trim();

        if (rawBody.length > 0) {
            const pemLines = rawBody.match(/.{1,64}/g) ?? [rawBody];
            privateKey = `${beginMarker}\n${pemLines.join('\n')}\n${endMarker}`;
        } else {
            privateKey = privateKey.slice(beginIndex, endIndex + endMarker.length).trim();
        }
    }

    if (!privateKey.includes(beginMarker) || !privateKey.includes(endMarker)) {
        throw new Error('Invalid private key format. Paste the `private_key` value from your service account JSON.');
    }

    return privateKey;
}

/**
 * Validates GCP credentials by attempting to get access token
 */
export async function validateGcpCredentials(options: GcpCredentialOptions) {
    try {
        const projectId = options.projectId.trim();
        const serviceAccountEmail = options.serviceAccountEmail.trim();
        const privateKey = normalizePrivateKey(options.privateKey);

        // Create credentials object matching GCP service account format
        const credentials = {
            type: 'service_account',
            project_id: projectId,
            client_email: serviceAccountEmail,
            private_key: privateKey,
        };

        const auth = new GoogleAuth({
            credentials,
            scopes: ['https://www.googleapis.com/auth/cloud-platform.read-only'],
        });

        // Try to get an access token to verify credentials
        const client = await auth.getClient();
        await client.getAccessToken();

        return {
            valid: true,
            projectId,
            serviceAccountEmail,
            privateKey,
        };

    } catch (error: unknown) {
        let message = error instanceof Error ? error.message : "Failed to validate GCP credentials";
        if (message.includes('DECODER routines::unsupported')) {
            message = 'Invalid private key format. Paste only the `private_key` value (with BEGIN/END lines) from the service account JSON file.';
        }
        console.error("GCP Validation Error:", error);
        return {
            valid: false,
            error: message
        };
    }
}
