import crypto from 'crypto';

// Ensure this key is exactly 32 bytes (256 bits)
const ALGORITHM = 'aes-256-gcm';
const ENCODING = 'hex';
const IV_LENGTH = 12; // Recommended for GCM

function getDetails() {
    const secretKey = process.env.ENCRYPTION_KEY;
    if (!secretKey) {
        throw new Error('ENCRYPTION_KEY environment variable is not defined');
    }
    // If key is hex string, convert to buffer, otherwise assume string
    const key = Buffer.from(secretKey, secretKey.length === 64 ? 'hex' : 'utf-8');
    if (key.length !== 32) {
        throw new Error(`ENCRYPTION_KEY must be 32 bytes. Current length: ${key.length}`);
    }
    return { key };
}

export function encrypt(text: string): { encrypted: string; iv: string } {
    const { key } = getDetails();
    const iv = crypto.randomBytes(IV_LENGTH);
    const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

    let encrypted = cipher.update(text, 'utf8', ENCODING);
    encrypted += cipher.final(ENCODING);

    // Auth tag is critical for GCM integrity check
    const authTag = cipher.getAuthTag().toString(ENCODING);

    // Return encrypted content + auth tag + iv
    // Format: encrypted_content:auth_tag
    // IV is returned separately/stored separately
    return {
        encrypted: `${encrypted}:${authTag}`,
        iv: iv.toString(ENCODING),
    };
}

export function decrypt(encryptedData: string, ivHex: string): string {
    const { key } = getDetails();
    const [encryptedText, authTagHex] = encryptedData.split(':');

    if (!encryptedText || !authTagHex) {
        throw new Error('Invalid encrypted data format');
    }

    const decipher = crypto.createDecipheriv(ALGORITHM, key, Buffer.from(ivHex, ENCODING));
    decipher.setAuthTag(Buffer.from(authTagHex, ENCODING));

    let decrypted = decipher.update(encryptedText, ENCODING, 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
}
