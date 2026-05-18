'use server';

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "@/app/api/_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export async function askWatchdog(message: string, context: { session_id?: string }) {
    const authContext = await getBackendAuthContext();
    if (!authContext?.userId) {
        return { success: false, response: "Please log in to consult Clousy.", session_id: "" };
    }

    try {
        const chatUrl = `${BACKEND_URL}/api/agent/chat`;

        if (!hasBackendAuthCandidate(chatUrl, authContext)) {
            return {
                success: false,
                response: "Unable to authenticate with the AI backend. Please refresh and try again.",
                session_id: context.session_id || "",
            };
        }

        const res = await fetchWithBackendAuthFallback(fetch, chatUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                session_id: context.session_id || undefined,
            }),
        }, authContext);

        if (!res.ok) {
            const errorText = await res.text();
            if (res.status === 401 || res.status === 403) {
                return {
                    success: false,
                    response: "Unable to authenticate with the AI backend. Please refresh and try again.",
                    session_id: context.session_id || "",
                };
            }
            console.error("Agent API error:", res.status, errorText);
            return {
                success: false,
                response: "Failed to reach the AI agent. Please ensure the backend is running.",
                session_id: context.session_id || "",
            };
        }

        if (!res.body) {
            return {
                success: false,
                response: "AI backend returned no stream body.",
                session_id: context.session_id || "",
            };
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";
        let buffer = "";
        let finalSessionId = context.session_id || "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
                const lines = part.split("\n");
                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === "chunk" && typeof data.content === "string") {
                            fullText += data.content;
                        } else if (data.type === "error" && typeof data.content === "string") {
                            fullText = data.content;
                        } else if (data.type === "done" && typeof data.session_id === "string") {
                            finalSessionId = data.session_id;
                        }
                    } catch {
                        // Ignore malformed chunks
                    }
                }
            }
        }

        if (!fullText.trim()) {
            fullText = "I didn't receive a response from Clousy. Please try again.";
        }

        return {
            success: true,
            response: fullText,
            session_id: finalSessionId,
        };
    } catch (e) {
        console.error("Watchdog Action Error:", e);
        return {
            success: false,
            response: "Could not connect to the AI agent backend.",
            session_id: context.session_id || "",
        };
    }
}
