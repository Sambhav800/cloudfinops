export type BackendAuthContext = {
    token: string | null;
    userId: string | null;
};

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

function toRecord(headers?: HeadersInit): Record<string, string> {
    if (!headers) {
        return {};
    }

    if (headers instanceof Headers) {
        return Object.fromEntries(headers.entries());
    }

    if (Array.isArray(headers)) {
        return Object.fromEntries(headers);
    }

    return { ...headers };
}

export function buildBackendAuthHeaders(
    url: string,
    authContext: BackendAuthContext,
    headers?: HeadersInit,
    fallbackUserId?: string | null,
): Record<string, string> {
    const baseHeaders = toRecord(headers);

    if (authContext.token) {
        return {
            ...baseHeaders,
            Authorization: `Bearer ${authContext.token}`,
        };
    }

    return baseHeaders;
}

export function hasBackendAuthCandidate(
    url: string,
    authContext: BackendAuthContext,
    fallbackUserId?: string | null,
): boolean {
    return Boolean(authContext.token);
}

export async function fetchWithBackendAuthFallback(
    fetchImpl: FetchLike,
    url: string,
    init: RequestInit,
    authContext: BackendAuthContext,
    fallbackUserId?: string | null,
): Promise<Response> {
    const baseHeaders = toRecord(init.headers);
    const headerCandidates: Record<string, string>[] = [];

    if (authContext.token) {
        headerCandidates.push({
            ...baseHeaders,
            Authorization: `Bearer ${authContext.token}`,
        });
    }

    if (headerCandidates.length === 0) {
        return fetchImpl(url, init);
    }

    let lastResponse: Response | null = null;
    for (const headers of headerCandidates) {
        const response = await fetchImpl(url, {
            ...init,
            headers,
        });

        if (response.status !== 401) {
            return response;
        }
        lastResponse = response;
    }

    return lastResponse as Response;
}
