"use client";

import { useState, useRef, useEffect, useCallback, createContext, useContext } from "react";
import { Send, X, CloudLightning, Copy, Check, Maximize2, Minimize2, Download, PanelRightOpen, PanelRightClose, FileCode2, MessageSquareText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useUser, useAuth } from "@clerk/nextjs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SyntaxHighlighter from "react-syntax-highlighter/dist/cjs/prism";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";

// ─── Types ──────────────────────────────────────────────────────
interface Message {
    id: number;
    role: "user" | "ai";
    content: string;
}

type AgentPillName = "Savings Agent" | "Governance Agent" | "Bill Agent";

interface AgentStatus {
    name: AgentPillName;
    status: "idle" | "scanning";
    insights_ready: number;
}

// ─── Canvas Context ─────────────────────────────────────────────
interface CanvasState {
    code: string;
    language: string;
    title?: string;
}

const CanvasContext = createContext<{
    openCanvas: (state: CanvasState) => void;
}>({ openCanvas: () => { } });

// ─── Copy Button ────────────────────────────────────────────────
function CopyButton({ text, size = "sm" }: { text: string; size?: "sm" | "md" }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [text]);

    const cls = size === "md"
        ? "px-2.5 py-1 text-[11px] gap-1.5"
        : "px-2 py-0.5 text-[10px] gap-1";

    return (
        <button
            onClick={handleCopy}
            className={`flex items-center ${cls} font-medium rounded-md transition-all duration-150 text-slate-400 hover:text-white hover:bg-white/10`}
            title="Copy"
        >
            {copied ? (
                <><Check className="w-3 h-3 text-emerald-400" /><span className="text-emerald-400">Copied</span></>
            ) : (
                <><Copy className="w-3 h-3" /><span>Copy</span></>
            )}
        </button>
    );
}

// ─── Canvas Panel (slide-in right panel) ────────────────────────
function CanvasPanel({
    code,
    language,
    title,
    onClose,
}: {
    code: string;
    language: string;
    title?: string;
    onClose: () => void;
}) {
    const handleDownload = useCallback(() => {
        const ext: Record<string, string> = {
            python: "py", javascript: "js", typescript: "ts", bash: "sh",
            shell: "sh", json: "json", yaml: "yml", yml: "yml", sql: "sql",
            hcl: "tf", terraform: "tf", dockerfile: "Dockerfile", go: "go",
            css: "css", html: "html", markdown: "md", text: "txt",
        };
        const fileExt = ext[language.toLowerCase()] || "txt";
        const blob = new Blob([code], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `clousy-${language}.${fileExt}`;
        a.click();
        URL.revokeObjectURL(url);
    }, [code, language]);

    const [isExpanded, setIsExpanded] = useState(false);
    const [wrapLongLines, setWrapLongLines] = useState(false);
    const normalizedLanguage = language.toLowerCase();
    const isPlainText = ["text", "txt", "markdown", "md", "log"].includes(normalizedLanguage);
    const lineCount = code.split("\n").length;

    return (
        <motion.div
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="absolute inset-y-0 right-0 z-20 flex flex-col bg-[#0d1117] border-l border-white/[0.06]"
            style={{ width: isExpanded ? "100%" : "clamp(360px, 62%, 780px)" }}
        >
            {/* Canvas Header */}
            <div className="flex items-center justify-between px-3.5 py-2.5 bg-[#161b22] border-b border-white/[0.06] shrink-0">
                <div className="flex items-center gap-2.5">
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-cyan-500/10 border border-cyan-500/15">
                        <FileCode2 className="w-3 h-3 text-cyan-400" />
                        <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider">
                            {language}
                        </span>
                    </div>
                    {title && (
                        <span className="text-[11px] text-slate-400 font-medium truncate max-w-[150px]">
                            {title}
                        </span>
                    )}
                    <span className="text-[10px] text-slate-600 font-mono">
                        {lineCount} lines
                    </span>
                </div>
                <div className="flex items-center gap-0.5">
                    <button
                        onClick={() => setWrapLongLines((value) => !value)}
                        className={`flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md transition-all ${wrapLongLines
                            ? "text-cyan-300 bg-cyan-500/10 border border-cyan-500/20"
                            : "text-slate-400 hover:text-white hover:bg-white/10"
                            }`}
                        title={wrapLongLines ? "Disable wrap" : "Enable wrap"}
                    >
                        {wrapLongLines ? "No Wrap" : "Wrap"}
                    </button>
                    <button
                        onClick={() => setIsExpanded((value) => !value)}
                        className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-slate-400 hover:text-white hover:bg-white/10 rounded-md transition-all"
                        title={isExpanded ? "Reduce canvas" : "Expand canvas"}
                    >
                        {isExpanded ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                    </button>
                    <button
                        onClick={handleDownload}
                        className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-slate-400 hover:text-white hover:bg-white/10 rounded-md transition-all"
                        title="Download"
                    >
                        <Download className="w-3 h-3" />
                    </button>
                    <CopyButton text={code} size="sm" />
                    <button
                        onClick={onClose}
                        className="ml-1 p-1 text-slate-500 hover:text-white hover:bg-white/10 rounded-md transition-all"
                        title="Close canvas"
                    >
                        <PanelRightClose className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* Canvas Code Body */}
            <div className="flex-1 overflow-auto [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-slate-700/40 [&::-webkit-scrollbar-thumb]:rounded-full" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(51,65,85,0.4) transparent' }}>
                {isPlainText ? (
                    <pre
                        className={`m-0 px-4 py-3 text-[12px] leading-6 text-slate-200 font-mono ${wrapLongLines
                            ? "whitespace-pre-wrap break-words"
                            : "whitespace-pre min-w-fit"
                            }`}
                    >
                        {code || "// empty"}
                    </pre>
                ) : (
                    <SyntaxHighlighter
                        style={oneDark}
                        language={language}
                        showLineNumbers
                        wrapLongLines={wrapLongLines}
                        lineNumberStyle={{
                            minWidth: "2.5em",
                            paddingRight: "1em",
                            color: "#3d4450",
                            fontStyle: "normal",
                            userSelect: "none",
                        }}
                        customStyle={{
                            margin: 0,
                            padding: "0.9rem 0.9rem",
                            background: "transparent",
                            fontSize: "0.82rem",
                            lineHeight: "1.68",
                        }}
                        codeTagProps={{
                            style: {
                                fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
                                whiteSpace: wrapLongLines ? "pre-wrap" : "pre",
                                wordBreak: wrapLongLines ? "break-word" : "normal",
                            },
                        }}
                    >
                        {code}
                    </SyntaxHighlighter>
                )}
            </div>

            {/* Canvas Footer */}
            <div className="px-3.5 py-2 bg-[#161b22] border-t border-white/[0.06] flex items-center justify-between shrink-0">
                <span className="text-[9px] text-slate-600 flex items-center gap-1">
                    <CloudLightning className="w-2.5 h-2.5 text-cyan-500/40" />
                    Clousy Canvas • {wrapLongLines ? "Wrap On" : "Wrap Off"}
                </span>
                <span className="text-[9px] text-slate-600">
                    <kbd className="px-1 py-0.5 bg-white/5 rounded text-slate-500 font-mono text-[8px]">Esc</kbd> close
                </span>
            </div>
        </motion.div>
    );
}

// ─── Markdown renderer ─────────────────────────────────────────
function MarkdownContent({ content }: { content: string }) {
    const { openCanvas } = useContext(CanvasContext);

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                code({ className, children, ...rest }) {
                    const match = (className || "").match(/language-(\w+)/);
                    const codeString = String(children || "").replace(/\n$/, "");

                    if (match || codeString.includes("\n")) {
                        const lang = match?.[1] || "text";
                        return (
                            <div className="my-2 rounded-lg overflow-hidden border border-white/[0.06] bg-[#0d1117] group/code">
                                <div className="flex items-center justify-between px-3 py-1.5 bg-white/[0.02] border-b border-white/[0.05]">
                                    <span className="text-[10px] font-mono font-semibold text-cyan-500/70 uppercase tracking-widest">
                                        {lang}
                                    </span>
                                    <div className="flex items-center gap-0.5">
                                        <CopyButton text={codeString} />
                                        <button
                                            onClick={() => openCanvas({
                                                code: codeString,
                                                language: lang,
                                                title: `${lang.toUpperCase()} Snippet`,
                                            })}
                                            className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-md transition-all duration-150 text-slate-500 hover:text-cyan-400 hover:bg-white/10"
                                            title="Open in Canvas"
                                        >
                                            <PanelRightOpen className="w-3 h-3" />
                                            <span>Canvas</span>
                                        </button>
                                    </div>
                                </div>
                                <div className="overflow-x-auto max-h-[280px] overflow-y-auto [&::-webkit-scrollbar]:h-1 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-slate-700/40 [&::-webkit-scrollbar-thumb]:rounded-full" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(51,65,85,0.4) transparent' }}>
                                    <SyntaxHighlighter
                                        style={oneDark}
                                        language={lang}
                                        showLineNumbers
                                        lineNumberStyle={{
                                            minWidth: "2em",
                                            paddingRight: "0.75em",
                                            color: "#3d4450",
                                            fontStyle: "normal",
                                            userSelect: "none",
                                        }}
                                        PreTag="div"
                                        customStyle={{
                                            margin: 0,
                                            padding: "0.5rem 0.75rem",
                                            background: "transparent",
                                            fontSize: "0.75rem",
                                            lineHeight: "1.6",
                                        }}
                                        codeTagProps={{
                                            style: {
                                                fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
                                                whiteSpace: "pre",
                                                wordBreak: "normal" as const,
                                            },
                                        }}
                                    >
                                        {codeString || "// empty"}
                                    </SyntaxHighlighter>
                                </div>
                            </div>
                        );
                    }

                    return (
                        <code
                            className="px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-300 text-[0.8em] font-mono border border-cyan-500/8"
                            {...rest}
                        >
                            {children}
                        </code>
                    );
                },

                h1: ({ children }) => (
                    <h1 className="text-[13px] font-bold text-white mt-3 mb-1.5 pb-1 border-b border-white/[0.06]">{children}</h1>
                ),
                h2: ({ children }) => (
                    <h2 className="text-[13px] font-bold text-white mt-2.5 mb-1.5">{children}</h2>
                ),
                h3: ({ children }) => (
                    <h3 className="text-[12px] font-bold text-cyan-300 mt-2 mb-1">{children}</h3>
                ),
                h4: ({ children }) => (
                    <h4 className="text-[12px] font-semibold text-cyan-200 mt-1.5 mb-1 flex items-center gap-1.5">
                        <span className="w-1 h-1 rounded-full bg-cyan-400/60" />
                        {children}
                    </h4>
                ),

                p: ({ children }) => <p className="leading-relaxed text-slate-300 mb-1.5 last:mb-0 text-[13px]">{children}</p>,

                ul: ({ children }) => <ul className="space-y-1 mb-2 ml-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="space-y-1 mb-2 ml-0.5 list-none">{children}</ol>,
                li: ({ children }) => (
                    <li className="flex gap-1.5 text-slate-300 leading-relaxed text-[12px]">
                        <span className="text-cyan-500/60 mt-0.5 shrink-0 text-[10px]">•</span>
                        <span className="flex-1">{children}</span>
                    </li>
                ),

                strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                em: ({ children }) => <em className="text-cyan-200/80 not-italic font-medium">{children}</em>,

                a: ({ children, href }) => (
                    <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-400 underline underline-offset-2 decoration-cyan-400/30 hover:text-cyan-300 transition-colors text-[12px]"
                    >
                        {children}
                    </a>
                ),

                table: ({ children }) => (
                    <div className="overflow-x-auto my-2 rounded-lg border border-white/[0.06]">
                        <table className="w-full text-[11px] text-left border-collapse">{children}</table>
                    </div>
                ),
                thead: ({ children }) => (
                    <thead className="bg-cyan-500/[0.06] text-cyan-300/80 text-[10px] uppercase tracking-wider border-b border-white/[0.06]">
                        {children}
                    </thead>
                ),
                tbody: ({ children }) => (
                    <tbody className="divide-y divide-white/[0.03] bg-[#0a0f1a]/40">{children}</tbody>
                ),
                tr: ({ children }) => (
                    <tr className="hover:bg-cyan-500/[0.03] transition-colors">{children}</tr>
                ),
                th: ({ children }) => (
                    <th className="px-2.5 py-2 font-semibold whitespace-nowrap">{children}</th>
                ),
                td: ({ children }) => (
                    <td className="px-2.5 py-1.5 text-slate-300">{children}</td>
                ),

                blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-amber-500/50 bg-amber-500/[0.04] rounded-r-md pl-3 pr-2 py-2 my-2 text-slate-300 text-[12px]">
                        {children}
                    </blockquote>
                ),

                hr: () => <hr className="my-3 border-white/[0.05]" />,
            }}
        >
            {content}
        </ReactMarkdown>
    );
}

// ─── Suggestion Chips ───────────────────────────────────────────
const SUGGESTIONS = [
    "What's my biggest cost driver this month?",
    "Show me all zombie and idle resources",
    "How do I optimize my Savings Plan coverage?",
    "Which team is spending the most?",
    "What should I fix first to save the most money?",
];

const DEFAULT_AGENT_STATUSES: AgentStatus[] = [
    { name: "Savings Agent", status: "idle", insights_ready: 0 },
    { name: "Governance Agent", status: "idle", insights_ready: 0 },
    { name: "Bill Agent", status: "idle", insights_ready: 0 },
];

const AGENT_MODE_HINTS: Record<AgentPillName, string> = {
    "Savings Agent": "Focus strictly on savings, cost optimization, waste detection, rightsizing, budgets, and commitment coverage using the user's live CloudFinOps data.",
    "Governance Agent": "Focus strictly on governance, compliance, policy violations, audit context, and security or permission findings from the user's live CloudFinOps data.",
    "Bill Agent": "Focus strictly on bill analyses, uploaded invoices, category spend, credits, savings already active, and executive bill-report insights from the user's live CloudFinOps data.",
};

function normalizeAgentStatuses(payload: unknown): AgentStatus[] {
    if (!payload || typeof payload !== "object" || !("agents" in payload)) {
        return DEFAULT_AGENT_STATUSES;
    }

    const agents = Array.isArray((payload as { agents?: unknown[] }).agents)
        ? (payload as { agents: unknown[] }).agents
        : [];

    const mapped = new Map<AgentPillName, AgentStatus>();
    for (const item of agents) {
        if (!item || typeof item !== "object") continue;
        const name = (item as { name?: unknown }).name;
        const status = (item as { status?: unknown }).status;
        const insightsReady = (item as { insights_ready?: unknown }).insights_ready;

        if (
            (name === "Savings Agent" || name === "Governance Agent" || name === "Bill Agent") &&
            (status === "idle" || status === "scanning")
        ) {
            mapped.set(name, {
                name,
                status,
                insights_ready: typeof insightsReady === "number" && Number.isFinite(insightsReady)
                    ? Math.max(0, Math.round(insightsReady))
                    : 0,
            });
        }
    }

    return DEFAULT_AGENT_STATUSES.map((fallback) => mapped.get(fallback.name) ?? fallback);
}

function getAgentStatusText(agent: AgentStatus) {
    if (agent.insights_ready > 0) {
        return `${agent.insights_ready} insight${agent.insights_ready === 1 ? "" : "s"} ready`;
    }
    return agent.status === "scanning" ? "Scanning..." : "Idle";
}

function buildScopedMessage(agentName: AgentPillName | null, message: string) {
    if (!agentName) {
        return message;
    }

    return [
        `Agent mode: ${agentName}`,
        AGENT_MODE_HINTS[agentName],
        `User request: ${message}`,
    ].join("\n\n");
}

// ─── Single Chat Message ────────────────────────────────────────
function ChatMessage({ msg }: { msg: Message }) {
    const isAI = msg.role === "ai";

    if (!isAI) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.15 }}
                className="flex justify-end"
            >
                <div className="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-br-md bg-gradient-to-r from-indigo-600/90 to-blue-600/90 text-white text-[13px] leading-relaxed shadow-[0_8px_26px_rgba(37,99,235,0.35)] border border-indigo-400/15">
                    {msg.content}
                </div>
            </motion.div>
        );
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
            className="flex items-start gap-2.5"
        >
            <div className="p-1.5 rounded-lg shrink-0 bg-slate-800/60 border border-white/[0.06] mt-0.5">
                <CloudLightning className="w-3.5 h-3.5 text-cyan-400" />
            </div>
            <div className="flex-1 min-w-0 rounded-2xl rounded-tl-md border border-white/[0.06] border-l-2 border-indigo-500/30 bg-[#0a0f1a]/62 px-3.5 py-2.5 shadow-[0_10px_30px_rgba(2,6,16,0.38)]">
                <MarkdownContent content={msg.content} />
            </div>
        </motion.div>
    );
}

// ─── Welcome Screen ─────────────────────────────────────────────
function WelcomeScreen({
    userName,
    accountSummary,
    isSummaryLoading,
    onSuggestionClick,
}: {
    userName: string;
    accountSummary: string;
    isSummaryLoading: boolean;
    onSuggestionClick: (s: string) => void;
}) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.3 }}
            className="flex h-full flex-col justify-center px-6"
        >
            <div className="mx-auto w-full max-w-[360px] space-y-5">
                <div className="flex items-start gap-2.5">
                    <div className="mt-0.5 rounded-lg border border-white/[0.06] bg-slate-800/60 p-1.5 shrink-0">
                        <CloudLightning className="w-3.5 h-3.5 text-cyan-400" />
                    </div>
                    <div className="flex-1 rounded-2xl rounded-tl-md border border-white/[0.06] border-l-2 border-indigo-500/30 bg-[#0a0f1a]/62 px-4 py-3 shadow-[0_10px_30px_rgba(2,6,16,0.38)]">
                        <p className="text-[12px] font-medium text-indigo-300">
                            Clousy
                        </p>
                        {isSummaryLoading ? (
                            <div className="mt-2 space-y-2">
                                <div className="h-3.5 w-4/5 animate-pulse rounded-full bg-white/[0.06]" />
                                <div className="h-3.5 w-full animate-pulse rounded-full bg-white/[0.05]" />
                                <div className="h-3.5 w-3/4 animate-pulse rounded-full bg-white/[0.04]" />
                            </div>
                        ) : (
                            <p className="mt-2 text-[13px] leading-relaxed text-slate-300">
                                {accountSummary || `${userName}, I'm ready. Ask me about costs, waste, commitments, or governance and I'll use your live CloudFinOps data.`}
                            </p>
                        )}
                    </div>
                </div>

                <div>
                    <p className="mb-2 text-[11px] uppercase tracking-[0.2em] text-slate-500">
                        Quick actions
                    </p>
                    <div className="space-y-2">
                        {SUGGESTIONS.map((s) => (
                            <button
                                key={s}
                                onClick={() => onSuggestionClick(s)}
                                className="w-full text-left px-3.5 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-slate-300 text-[12px] leading-relaxed hover:bg-white/[0.06] hover:border-white/[0.1] hover:text-white transition-all duration-150 group"
                            >
                                <span className="flex items-center gap-2">
                                    <MessageSquareText className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 transition-colors shrink-0" />
                                    {s}
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            </div>
        </motion.div>
    );
}

// ─── Main Drawer Component ──────────────────────────────────────
export function WatchdogModal({
    isOpen,
    onClose,
    context,
}: {
    isOpen: boolean;
    onClose: () => void;
    context: Record<string, unknown>;
}) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | undefined>(undefined);
    const [canvas, setCanvas] = useState<CanvasState | null>(null);
    const [accountSummary, setAccountSummary] = useState("");
    const [isSummaryLoading, setIsSummaryLoading] = useState(false);
    const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(DEFAULT_AGENT_STATUSES);
    const [isAgentStatusLoading, setIsAgentStatusLoading] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<AgentPillName | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const { user } = useUser();
    const { getToken } = useAuth();

    const hasMessages = messages.length > 0;

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading, scrollToBottom]);

    useEffect(() => {
        if (isOpen) inputRef.current?.focus();
    }, [isOpen]);

    useEffect(() => {
        if (!isOpen || hasMessages) {
            return;
        }

        let isCancelled = false;
        setIsSummaryLoading(true);

        fetch("/api/agent/summary", { cache: "no-store" })
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`summary ${r.status}`))))
            .then((data) => {
                if (!isCancelled) {
                    setAccountSummary(typeof data.summary === "string" ? data.summary : "");
                }
            })
            .catch(() => {
                if (!isCancelled) {
                    setAccountSummary("");
                }
            })
            .finally(() => {
                if (!isCancelled) {
                    setIsSummaryLoading(false);
                }
            });

        return () => {
            isCancelled = true;
        };
    }, [isOpen, hasMessages]);

    useEffect(() => {
        if (!isOpen) {
            return;
        }

        let isCancelled = false;
        let intervalId: ReturnType<typeof setInterval> | null = null;

        const loadAgentStatuses = async () => {
            if (!isCancelled) {
                setIsAgentStatusLoading(true);
            }

            try {
                const response = await fetch("/api/agents/status", { cache: "no-store" });
                if (!response.ok) {
                    throw new Error(`status ${response.status}`);
                }
                const payload = await response.json();
                if (!isCancelled) {
                    setAgentStatuses(normalizeAgentStatuses(payload));
                }
            } catch {
                if (!isCancelled) {
                    setAgentStatuses(DEFAULT_AGENT_STATUSES);
                }
            } finally {
                if (!isCancelled) {
                    setIsAgentStatusLoading(false);
                }
            }
        };

        void loadAgentStatuses();
        intervalId = setInterval(() => {
            void loadAgentStatuses();
        }, 15000);

        return () => {
            isCancelled = true;
            if (intervalId) {
                clearInterval(intervalId);
            }
        };
    }, [isOpen]);

    // Esc to close canvas
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && canvas) {
                setCanvas(null);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [canvas]);

    const handleSend = async (overrideMsg?: string) => {
        const msgText = overrideMsg || input.trim();
        if (!msgText || isLoading) return;
        const scopedMessage = buildScopedMessage(selectedAgent, msgText);

        const userMsg: Message = { id: Date.now(), role: "user", content: msgText };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setIsLoading(true);

        const aiMsgId = Date.now() + 1;
        setMessages((prev) => [...prev, { id: aiMsgId, role: "ai", content: "" }]);

        try {
            let token = await getToken();
            if (!token) {
                try {
                    token = await getToken({ template: "default" });
                } catch {
                    token = null;
                }
            }

            const headers: Record<string, string> = {
                "Content-Type": "application/json",
            };
            if (token) {
                headers.Authorization = `Bearer ${token}`;
            }

            // Same-origin API route — proxies SSE through Next.js server (no CORS)
            const res = await fetch("/api/agent/chat", {
                method: "POST",
                headers,
                body: JSON.stringify({
                    message: scopedMessage,
                    session_id: sessionId,
                }),
            });

            if (!res.ok) throw new Error("Network response was not ok");
            if (!res.body) throw new Error("No readable stream");

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let currentMessage = "";
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\n\n");
                buffer = parts.pop() || "";

                for (const part of parts) {
                    const lines = part.split("\n");
                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                if (data.type === "chunk") {
                                    currentMessage += data.content;
                                    setMessages((prev) =>
                                        prev.map((msg) => msg.id === aiMsgId ? { ...msg, content: currentMessage } : msg)
                                    );
                                } else if (data.type === "error") {
                                    currentMessage = data.content;
                                    setMessages((prev) =>
                                        prev.map((msg) => msg.id === aiMsgId ? { ...msg, content: currentMessage } : msg)
                                    );
                                } else if (data.type === "done") {
                                    if (data.session_id) setSessionId(data.session_id);
                                }
                            } catch {
                                // Skip malformed SSE chunks
                            }
                        }
                    }
                }
            }

            // Fallback: if stream ended without any content, show a helpful message
            if (!currentMessage) {
                setMessages((prev) =>
                    prev.map((msg) => msg.id === aiMsgId ? { ...msg, content: "I didn't receive a response. The AI backend may be processing your request or restarting. Please try again in a moment." } : msg)
                );
            }
        } catch {
            setMessages((prev) =>
                prev.map((msg) => msg.id === aiMsgId ? { ...msg, content: "Connection error. Please check that the backend is running and try again." } : msg)
            );
        } finally {
            setIsLoading(false);
        }
    };

    void context;

    const userName = user?.firstName || "there";

    return (
        <CanvasContext.Provider value={{ openCanvas: setCanvas }}>
            <AnimatePresence>
                {isOpen && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.15 }}
                            onClick={onClose}
                            className="fixed inset-0 z-[9998] bg-black/30 backdrop-blur-sm"
                        />

                        {/* Drawer */}
                        <motion.div
                            initial={{ x: "100%" }}
                            animate={{ x: 0 }}
                            exit={{ x: "100%" }}
                            transition={{ type: "spring", damping: 28, stiffness: 280 }}
                            className="fixed inset-y-0 right-0 z-[9999] flex flex-col"
                            style={{ width: "clamp(400px, 36vw, 700px)" }}
                        >
                            <div className="h-full flex flex-col bg-[#020610]/[0.98] border-l border-white/[0.06] shadow-[-12px_0_40px_rgba(0,0,0,0.4)] backdrop-blur-2xl relative overflow-hidden">
                                {/* Subtle ambient glows */}
                                <div className="absolute top-0 right-0 w-48 h-48 bg-cyan-500/[0.04] rounded-full blur-[80px] pointer-events-none" />
                                <div className="absolute bottom-0 left-0 w-48 h-48 bg-indigo-500/[0.04] rounded-full blur-[80px] pointer-events-none" />

                                {/* ── Header ── */}
                                <div className="px-4 py-3 border-b border-white/[0.06] flex justify-between items-center bg-black/20 z-10 shrink-0">
                                    <div className="flex items-center gap-2.5">
                                        <div className="relative">
                                            <div className="p-1.5 bg-slate-800/80 rounded-lg border border-white/[0.08]">
                                                <CloudLightning className="w-4 h-4 text-cyan-400" />
                                            </div>
                                            <span className="absolute -bottom-0.5 -right-0.5 flex h-2 w-2">
                                                <span className="animate-ping absolute inset-0 rounded-full bg-emerald-400 opacity-50" />
                                                <span className="relative rounded-full h-2 w-2 bg-emerald-500" />
                                            </span>
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-white text-[13px] leading-none flex items-center gap-1.5">
                                                Clousy
                                                <span className="px-1 py-px rounded text-[8px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/15 leading-none">
                                                    PRO
                                                </span>
                                            </h3>
                                            <p className="text-[10px] text-slate-500 mt-0.5">
                                                Gemini AI Core • Online
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={onClose}
                                        className="p-1.5 hover:bg-white/5 rounded-lg text-slate-500 hover:text-white transition-all"
                                        aria-label="Close Clousy"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>

                                {/* ── Content Area (messages + canvas side-by-side) ── */}
                                <div className="flex-1 flex relative overflow-hidden">
                                    {/* Messages Column */}
                                    <div className={`flex-1 flex flex-col min-w-0 transition-all duration-300 ${canvas ? "max-w-[42%]" : ""}`}>
                                        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 z-10 relative [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-slate-800/50 [&::-webkit-scrollbar-thumb]:rounded-full" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(30,41,59,0.5) transparent' }}>
                                            {!hasMessages ? (
                                                <WelcomeScreen
                                                    userName={userName}
                                                    accountSummary={accountSummary}
                                                    isSummaryLoading={isSummaryLoading}
                                                    onSuggestionClick={(s) => handleSend(s)}
                                                />
                                            ) : (
                                                <>
                                                    {messages.map((msg) => (
                                                        <ChatMessage key={msg.id} msg={msg} />
                                                    ))}
                                                </>
                                            )}

                                            {isLoading && (
                                                <motion.div
                                                    initial={{ opacity: 0 }}
                                                    animate={{ opacity: 1 }}
                                                    className="flex"
                                                >
                                                    <div className="flex items-center gap-2 px-4 py-3 rounded-2xl rounded-tl-md border border-white/[0.06] bg-[#0a0f1a]/62 w-fit">
                                                        <div className="flex gap-1">
                                                            {[0, 1, 2].map((i) => (
                                                                <span
                                                                    key={i}
                                                                    className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
                                                                    style={{ animationDelay: `${i * 150}ms` }}
                                                                />
                                                            ))}
                                                        </div>
                                                        <span className="text-slate-400 text-xs">Clousy is thinking...</span>
                                                    </div>
                                                </motion.div>
                                            )}
                                            <div ref={messagesEndRef} />
                                        </div>
                                    </div>

                                    {/* Canvas Panel */}
                                    <AnimatePresence>
                                        {canvas && (
                                            <CanvasPanel
                                                code={canvas.code}
                                                language={canvas.language}
                                                title={canvas.title}
                                                onClose={() => setCanvas(null)}
                                            />
                                        )}
                                    </AnimatePresence>
                                </div>

                                {/* ── Input ── */}
                                <div className="px-4 py-3 border-t border-white/[0.06] bg-black/20 z-10 shrink-0">
                                    <div className="mb-3">
                                        <div className="mb-2 flex items-center justify-between gap-3">
                                            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
                                                Agent Mode
                                            </p>
                                            {selectedAgent ? (
                                                <button
                                                    type="button"
                                                    onClick={() => setSelectedAgent(null)}
                                                    className="text-[10px] font-medium text-slate-500 hover:text-white transition-colors"
                                                >
                                                    Clear filter
                                                </button>
                                            ) : null}
                                        </div>
                                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                                            {agentStatuses.map((agent) => {
                                                const isSelected = selectedAgent === agent.name;
                                                return (
                                                    <button
                                                        key={agent.name}
                                                        type="button"
                                                        onClick={() => setSelectedAgent((current) => current === agent.name ? null : agent.name)}
                                                        className={`rounded-xl border px-3 py-2 text-left transition-all ${isSelected
                                                            ? "border-indigo-500/40 bg-indigo-500/10"
                                                            : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.14] hover:bg-white/[0.05]"
                                                            }`}
                                                    >
                                                        <div className="flex items-center justify-between gap-2">
                                                            <span className={`text-[12px] font-medium ${isSelected ? "text-white" : "text-slate-300"}`}>
                                                                {agent.name}
                                                            </span>
                                                            <span
                                                                className={`h-2 w-2 rounded-full ${agent.insights_ready > 0
                                                                    ? "bg-emerald-400"
                                                                    : agent.status === "scanning"
                                                                        ? "bg-amber-400"
                                                                        : "bg-slate-600"
                                                                    } ${agent.status === "scanning" && agent.insights_ready === 0 ? "animate-pulse" : ""}`}
                                                            />
                                                        </div>
                                                        <p className={`mt-1 text-[11px] ${isSelected ? "text-indigo-200" : "text-slate-500"}`}>
                                                            {isAgentStatusLoading && agent.insights_ready === 0 && agent.status === "idle"
                                                                ? "Loading..."
                                                                : getAgentStatusText(agent)}
                                                        </p>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                    <div className="relative flex items-center bg-[#0a0f1a]/80 rounded-xl border border-white/[0.08] overflow-hidden focus-within:border-cyan-500/20 transition-colors">
                                        <input
                                            ref={inputRef}
                                            type="text"
                                            value={input}
                                            onChange={(e) => setInput(e.target.value)}
                                            onKeyDown={(e) => e.key === "Enter" && handleSend()}
                                            placeholder={selectedAgent ? `Ask ${selectedAgent}...` : "How can I assist you today?"}
                                            className="w-full bg-transparent pl-3.5 pr-12 py-2.5 text-[13px] text-white placeholder-slate-600 focus:outline-none"
                                            disabled={isLoading}
                                        />
                                        <button
                                            onClick={() => handleSend()}
                                            disabled={!input.trim() || isLoading}
                                            className="absolute right-2 p-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-0 disabled:scale-75 rounded-lg text-white transition-all duration-200"
                                        >
                                            <Send className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </CanvasContext.Provider>
    );
}
