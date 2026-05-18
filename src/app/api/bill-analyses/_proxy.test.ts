import assert from "node:assert/strict";
import test from "node:test";

async function loadHelper() {
    return import(new URL("../_shared/fetch-with-backend-auth-fallback.ts", import.meta.url).href);
}

test("does not retry with a user-id header when bearer auth returns 401", async () => {
    const { fetchWithBackendAuthFallback } = await loadHelper();
    const seenHeaders: Array<Record<string, string>> = [];

    const response = await fetchWithBackendAuthFallback(
        async (_url: string, init?: RequestInit) => {
            const headers = (init?.headers || {}) as Record<string, string>;
            seenHeaders.push(headers);

            return new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 });
        },
        "http://127.0.0.1:8000/api/bill-analyses/analysis-1",
        {
            method: "GET",
            cache: "no-store",
        },
        {
            token: "bad-token",
            userId: "user-123",
        },
    );

    assert.equal(response.status, 401);
    assert.deepEqual(seenHeaders, [{ Authorization: "Bearer bad-token" }]);
});

test("sends no auth header when no bearer token is available", async () => {
    const { fetchWithBackendAuthFallback } = await loadHelper();
    const seenHeaders: Array<Record<string, string>> = [];

    const response = await fetchWithBackendAuthFallback(
        async (_url: string, init?: RequestInit) => {
            const headers = (init?.headers || {}) as Record<string, string>;
            seenHeaders.push(headers);
            return new Response(JSON.stringify({ ok: true }), { status: 200 });
        },
        "http://localhost:8000/api/bill-analyses",
        {
            method: "GET",
            cache: "no-store",
        },
        {
            token: null,
            userId: "user-123",
        },
    );

    assert.equal(response.status, 200);
    assert.deepEqual(seenHeaders, [{}]);
});

test("does not emit fallback auth for remote backend URLs without a token", async () => {
    const { fetchWithBackendAuthFallback } = await loadHelper();
    const seenHeaders: Array<Record<string, string>> = [];

    const response = await fetchWithBackendAuthFallback(
        async (_url: string, init?: RequestInit) => {
            const headers = (init?.headers || {}) as Record<string, string>;
            seenHeaders.push(headers);
            return new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 });
        },
        "https://cloudfinops-backend.onrender.com/api/bill-analyses",
        {
            method: "GET",
            cache: "no-store",
        },
        {
            token: null,
            userId: "user-123",
        },
    );

    assert.equal(response.status, 401);
    assert.deepEqual(seenHeaders, [{}]);
});

test("treats only a bearer token as a valid backend auth candidate", async () => {
    const { hasBackendAuthCandidate } = await loadHelper();

    assert.equal(
        hasBackendAuthCandidate("http://127.0.0.1:8000/api/foo", { token: null, userId: "user-123" }),
        false,
    );
    assert.equal(
        hasBackendAuthCandidate("http://localhost:8000/api/foo", { token: null, userId: "user-123" }),
        false,
    );
    assert.equal(
        hasBackendAuthCandidate("https://cloudfinops-backend.onrender.com/api/foo", { token: null, userId: "user-123" }),
        false,
    );
});

test("treats a bearer token as a valid auth candidate for remote backends", async () => {
    const { hasBackendAuthCandidate } = await loadHelper();

    assert.equal(
        hasBackendAuthCandidate("https://cloudfinops-backend.onrender.com/api/foo", { token: "token-123", userId: "user-123" }),
        true,
    );
});

test("builds authorization headers for remote backends when a token is present", async () => {
    const { buildBackendAuthHeaders } = await loadHelper();

    assert.deepEqual(
        buildBackendAuthHeaders(
            "https://cloudfinops-backend.onrender.com/api/foo",
            { token: "token-123", userId: "user-123" },
            { "Content-Type": "application/json" },
        ),
        {
            "Content-Type": "application/json",
            Authorization: "Bearer token-123",
        },
    );
});

test("does not build local fallback headers when no token is present", async () => {
    const { buildBackendAuthHeaders } = await loadHelper();

    assert.deepEqual(
        buildBackendAuthHeaders(
            "http://localhost:3000/api/foo",
            { token: null, userId: "user-123" },
            { "Content-Type": "application/json" },
        ),
        {
            "Content-Type": "application/json",
        },
    );
    assert.deepEqual(
        buildBackendAuthHeaders(
            "https://cloudfinops.com/api/foo",
            { token: null, userId: "user-123" },
            { "Content-Type": "application/json" },
        ),
        {
            "Content-Type": "application/json",
        },
    );
});
