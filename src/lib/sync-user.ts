import { auth, currentUser } from "@clerk/nextjs/server";

import {
    fetchWithBackendAuthFallback,
    hasBackendAuthCandidate,
} from "@/app/api/_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

type SessionClaims = Record<string, unknown> | null | undefined;
type ClerkServerUser = Awaited<ReturnType<typeof currentUser>>;

function getClaimString(sessionClaims: SessionClaims, keys: string[]) {
    for (const key of keys) {
        const value = sessionClaims?.[key];
        if (typeof value === "string" && value.length > 0) {
            return value;
        }
    }

    return null;
}

function getClerkUserEmail(user: ClerkServerUser) {
    const primary = user?.primaryEmailAddress?.emailAddress;
    if (typeof primary === "string" && primary.length > 0) {
        return primary;
    }

    const fallback = user?.emailAddresses?.[0]?.emailAddress;
    if (typeof fallback === "string" && fallback.length > 0) {
        return fallback;
    }

    return null;
}

function getClerkUserNamePart(value: unknown) {
    return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function buildUserPayload(userId: string, sessionClaims: SessionClaims, clerkUser: ClerkServerUser) {
    const firstName =
        getClerkUserNamePart(clerkUser?.firstName) ??
        getClaimString(sessionClaims, ["given_name", "first_name"]);
    const lastName =
        getClerkUserNamePart(clerkUser?.lastName) ??
        getClaimString(sessionClaims, ["family_name", "last_name"]);
    const fallbackFullName = [firstName, lastName].filter(Boolean).join(" ").trim();
    const fullName =
        getClerkUserNamePart(clerkUser?.fullName) ??
        getClaimString(sessionClaims, ["full_name", "name"]) ??
        (fallbackFullName || null);

    return {
        id: userId,
        email: getClerkUserEmail(clerkUser) ?? getClaimString(sessionClaims, ["email", "email_address"]),
        first_name: firstName,
        last_name: lastName,
        full_name: fullName,
        avatar_url:
            getClerkUserNamePart(clerkUser?.imageUrl) ??
            getClaimString(sessionClaims, ["image_url", "picture"]),
        last_login: new Date().toISOString(),
    };
}

export async function syncUser() {
    try {
        const { userId, sessionClaims, getToken } = await auth();
        if (!userId) return null;

        let clerkUser: ClerkServerUser = null;
        try {
            clerkUser = await currentUser();
        } catch {
            clerkUser = null;
        }

        let token: string | null = null;
        try {
            token = await getToken();
        } catch {
            token = null;
        }

        if (!token) {
            try {
                token = await getToken({ template: "default" });
            } catch {
                token = null;
            }
        }

        const syncUrl = `${BACKEND_URL}/api/user/sync`;
        const authContext = { token, userId };

        if (!hasBackendAuthCandidate(syncUrl, authContext)) {
            return null;
        }

        const response = await fetchWithBackendAuthFallback(fetch, syncUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            cache: "no-store",
            body: JSON.stringify(
                buildUserPayload(userId, (sessionClaims ?? null) as SessionClaims, clerkUser),
            ),
        }, authContext);

        if (!response.ok) {
            const body = await response.text().catch(() => "");
            console.error("Error syncing user:", body || `status ${response.status}`);
            return null;
        }

        const result = await response.json().catch(() => null);
        if (result && typeof result.user_id === "string" && result.user_id.length > 0) {
            return result.user_id;
        }

        return userId;
    } catch (error) {
        console.error("Error syncing user:", error);
        return null;
    }
}
