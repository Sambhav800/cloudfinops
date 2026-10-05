import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import type { CommitmentRecommendationResponse } from "../../../lib/api";

const require = createRequire(import.meta.url);
const { NextRequest } = require("next/server") as typeof import("next/server");
const routePath = fileURLToPath(new URL("./route.ts", import.meta.url));
const payload: CommitmentRecommendationResponse = {
    status: "no_recommendations", source: "aws_cost_explorer", pricing_basis: "live_api",
    currency: "USD", fetched_at: "2026-09-16T03:00:00Z", generated_at: null,
    scenarios: [], recommended_scenario: null,
};

interface HarnessOptions {
    userId?: string | null;
    token?: string | null;
    fetchImpl?: typeof fetch;
    signals?: Pick<typeof AbortSignal, "timeout"> & Partial<Pick<typeof AbortSignal, "any">>;
}

// Execute the real route and shared auth helpers, replacing only Clerk, config, and fetch.
function loadRoute(options: HarnessOptions = {}): typeof import("./route") {
    const cache = new Map<string, { exports: Record<string, unknown> }>();
    function load(filename: string): Record<string, unknown> {
        const cached = cache.get(filename);
        if (cached) return cached.exports;
        const loaded = { exports: {} as Record<string, unknown> };
        cache.set(filename, loaded);
        const output = ts.transpileModule(readFileSync(filename, "utf8"), {
            compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
            fileName: filename,
        }).outputText;
        const localRequire = (name: string): unknown => {
            if (name === "@clerk/nextjs/server") return {
                auth: () => Promise.resolve({
                    userId: options.userId === undefined ? "test-user" : options.userId,
                    getToken: () => Promise.resolve(options.token === undefined ? "test-token" : options.token),
                }),
            };
            if (name === "@/lib/config") return { BACKEND_URL: "http://backend.invalid" };
            if (name.startsWith(".")) return load(resolve(dirname(filename), `${name}.ts`));
            return require(name);
        };
        new Function("require", "module", "exports", "fetch", "AbortSignal", output)(
            localRequire, loaded, loaded.exports,
            options.fetchImpl ?? (() => Promise.resolve(Response.json(payload))),
            options.signals ?? AbortSignal,
        );
        return loaded.exports;
    }
    return load(routePath) as typeof import("./route");
}

function request(query = "", signal = new AbortController().signal): InstanceType<typeof NextRequest> {
    return new NextRequest(`http://localhost:3000/api/commitment-recommendations${query}`, { signal });
}

function assertNoStore(response: Response): void {
    assert.equal(response.headers.get("Cache-Control"), "no-store");
}

function abortingFetch(onSignal: (signal: AbortSignal) => void): typeof fetch {
    return (_input, init) => new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal;
        assert.ok(signal);
        onSignal(signal);
        if (signal.aborted) reject(signal.reason);
        else signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });
}

test("Clerk user and backend token are both required, without fetching", async () => {
    try {
        for (const options of [{ userId: null }, { token: null }]) {
            let fetched = false;
            const { GET } = loadRoute({ ...options, fetchImpl: () => {
                fetched = true;
                return Promise.resolve(Response.json(payload));
            } });
            const response = await GET(request());
            assert.equal(response.status, 401);
            assert.deepEqual(await response.json(), { detail: "Unauthorized" });
            assert.equal(fetched, false);
            assertNoStore(response);
        }
    } catch (error) {
        throw error;
    }
});

test("scope and present legacy parameters are forwarded verbatim, including empty and repeated values", async () => {
    try {
        const queries = [
            "?integration_id=owned%2Fid&coverage_target=0&max_term=3&payment_option=NO_UPFRONT",
            "?integration_id=&coverage_target=&max_term=&payment_option=&ignored=drop",
            "?integration_id=owned-id&coverage_target=%20&coverage_target=&max_term&payment_option=%20NO_UPFRONT%20",
            "",
        ];
        for (const query of queries) {
            let target: URL | undefined;
            const { GET } = loadRoute({ fetchImpl: (input) => {
                target = new URL(String(input));
                return Promise.resolve(Response.json(payload));
            } });
            assert.equal((await GET(request(query))).status, 200);
            assert.ok(target);
            assert.equal(target.origin, "http://backend.invalid");
            assert.equal(target.pathname, "/api/commitment-recommendations");
            const expected = new URLSearchParams(query);
            expected.delete("ignored");
            assert.deepEqual([...target.searchParams], [...expected]);
        }
    } catch (error) {
        throw error;
    }
});

test("canonical success and empty alternatives pass through with no-store, bearer auth, and a bounded signal", async () => {
    try {
        const timeout = new AbortController();
        let timeoutMs: number | undefined;
        let fetched = false;
        const { GET } = loadRoute({
            signals: { any: AbortSignal.any, timeout: (ms) => { timeoutMs = ms; return timeout.signal; } },
            fetchImpl: (_input, init) => {
                fetched = true;
                assert.equal(init?.method, "GET");
                assert.equal(init.cache, "no-store");
                assert.equal(new Headers(init.headers).get("Authorization"), "Bearer test-token");
                assert.ok(init.signal instanceof AbortSignal);
                assert.equal(init.signal.aborted, false);
                return Promise.resolve(Response.json(payload));
            },
        });
        const response = await GET(request());
        assert.equal(fetched, true);
        assert.equal(timeoutMs, 15_000);
        assert.equal(response.status, 200);
        assertNoStore(response);
        assert.deepEqual(await response.json(), payload);
    } catch (error) {
        throw error;
    }
});

test("upstream 404 and structured legacy 422 errors retain their complete bodies and statuses", async () => {
    try {
        const errors = [
            { status: 404, body: { detail: "Owned integration not found", code: "not_found" } },
            { status: 422, body: { detail: [{ loc: ["query", "coverage_target"], type: "value_error", input: "", msg: "Legacy parameter unsupported" }], code: "legacy_parameters" } },
        ];
        for (const { status, body } of errors) {
            const { GET } = loadRoute({ fetchImpl: () => Promise.resolve(Response.json(body, { status })) });
            const response = await GET(request("?coverage_target="));
            assert.equal(response.status, status);
            assert.deepEqual(await response.json(), body);
            assertNoStore(response);
        }
    } catch (error) {
        throw error;
    }
});

test("malformed, null, primitive, and array success bodies return sanitized 502 errors", async () => {
    try {
        for (const body of ["not json with private details", "", "null", "[]", "42", "false", '"private details"']) {
            const { GET } = loadRoute({ fetchImpl: () => Promise.resolve(new Response(body)) });
            const response = await GET(request());
            assert.equal(response.status, 502);
            assert.deepEqual(await response.json(), { detail: "Commitment recommendations service returned invalid JSON" });
            assertNoStore(response);
        }
    } catch (error) {
        throw error;
    }
});

test("malformed upstream errors keep their status with a sanitized fallback body", async () => {
    try {
        const { GET } = loadRoute({ fetchImpl: () => Promise.resolve(new Response("private backend details", { status: 422 })) });
        const response = await GET(request());
        assert.equal(response.status, 422);
        assert.deepEqual(await response.json(), { detail: "Failed to load commitment recommendations" });
        assertNoStore(response);
    } catch (error) {
        throw error;
    }
});

test("15-second deadline aborts the upstream fetch and returns a sanitized 504", { timeout: 2_000 }, async () => {
    try {
        const timeout = new AbortController();
        const started = Promise.withResolvers<AbortSignal>();
        const { GET } = loadRoute({
            signals: { any: AbortSignal.any, timeout: (ms) => { assert.equal(ms, 15_000); return timeout.signal; } },
            fetchImpl: abortingFetch(started.resolve),
        });
        const pending = GET(request());
        const signal = await started.promise;
        timeout.abort(new DOMException("private timeout details", "TimeoutError"));
        const response = await pending;
        assert.equal(signal.aborted, true);
        assert.equal(response.status, 504);
        assert.deepEqual(await response.json(), { detail: "Commitment recommendations service timed out" });
        assertNoStore(response);
    } catch (error) {
        throw error;
    }
});

test("timeout during body parsing remains a 504, not invalid JSON", async () => {
    try {
        const timeout = new AbortController();
        const { GET } = loadRoute({
            signals: { any: AbortSignal.any, timeout: () => timeout.signal },
            fetchImpl: (_input, init) => {
                const response = new Response();
                response.json = () => {
                    timeout.abort(new DOMException("private timeout details", "TimeoutError"));
                    assert.equal(init?.signal?.aborted, true);
                    return Promise.reject(new DOMException("private body details", "AbortError"));
                };
                return Promise.resolve(response);
            },
        });
        const response = await GET(request());
        assert.equal(response.status, 504);
        assert.deepEqual(await response.json(), { detail: "Commitment recommendations service timed out" });
        assertNoStore(response);
    } catch (error) {
        throw error;
    }
});

test("network failures and non-Error rejections never expose raw details", async () => {
    try {
        for (const error of [new Error("secret-token http://private-backend.invalid"), "secret-token"]) {
            const { GET } = loadRoute({ fetchImpl: () => Promise.reject(error) });
            const response = await GET(request());
            assert.equal(response.status, 503);
            assert.deepEqual(await response.json(), { detail: "Could not reach the commitment recommendations service" });
            assertNoStore(response);
        }
    } catch (error) {
        throw error;
    }
});

test("request cancellation reaches the upstream signal and keeps the abort reason private", { timeout: 2_000 }, async () => {
    try {
        for (const alreadyAborted of [false, true]) {
            const controller = new AbortController();
            const reason = new DOMException("private cancellation details", "AbortError");
            if (alreadyAborted) controller.abort(reason);
            const started = Promise.withResolvers<AbortSignal>();
            const { GET } = loadRoute({ fetchImpl: abortingFetch(started.resolve) });
            const pending = GET(request("", controller.signal));
            const signal = await started.promise;
            controller.abort(reason);
            const response = await pending;
            assert.equal(signal.aborted, true);
            assert.equal(signal.reason, reason);
            assert.equal(response.status, 503);
            assert.deepEqual(await response.json(), { detail: "Could not reach the commitment recommendations service" });
            assertNoStore(response);
        }
    } catch (error) {
        throw error;
    }
});

test("runtimes without AbortSignal.any retain the 15-second timeout", async () => {
    try {
        const timeout = new AbortController();
        const { GET } = loadRoute({
            signals: { timeout: (ms) => { assert.equal(ms, 15_000); return timeout.signal; } },
            fetchImpl: (_input, init) => {
                assert.equal(init?.signal, timeout.signal);
                return Promise.resolve(Response.json(payload));
            },
        });
        const response = await GET(request());
        assert.equal(response.status, 200);
        assert.deepEqual(await response.json(), payload);
        assertNoStore(response);
    } catch (error) {
        throw error;
    }
});
