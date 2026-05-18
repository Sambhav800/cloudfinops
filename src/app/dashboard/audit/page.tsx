"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { useAuth } from "@clerk/nextjs"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { format } from "date-fns"
import { ShieldCheck, Activity, Terminal, AlertCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"

interface AuditLog {
    id: string
    action_type: string
    resource_target: string
    created_at: string
    metadata: Record<string, unknown> | null
}

export default function AuditLogsPage() {
    const { getToken } = useAuth()
    const [logs, setLogs] = useState<AuditLog[]>([])
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        async function fetchLogs() {
            try {
                let token = await getToken()
                if (!token) {
                    try {
                        token = await getToken({ template: "default" })
                    } catch {
                        token = null
                    }
                }

                const headers: Record<string, string> = {}
                if (token) {
                    headers.Authorization = `Bearer ${token}`
                }

                const res = await fetch(`/api/audit-logs?limit=50`, {
                    headers
                })
                const data = await res.json()
                if (data.logs) {
                    setLogs(data.logs)
                }
            } catch (e) {
                if (process.env.NODE_ENV === "development") {
                    console.error("Failed to fetch audit logs", e)
                }
            } finally {
                setIsLoading(false)
            }
        }
        fetchLogs()
    }, [getToken])

    const getActionIcon = (actionType: string) => {
        if (actionType.includes("SCAN")) return <Activity className="w-4 h-4 text-blue-400" />
        if (actionType.includes("CHAT") || actionType.includes("AI")) return <Terminal className="w-4 h-4 text-violet-400" />
        if (actionType.includes("USER")) return <ShieldCheck className="w-4 h-4 text-emerald-500" />
        return <AlertCircle className="w-4 h-4 text-slate-500" />
    }

    const getActionColor = (actionType: string) => {
        if (actionType.includes("SCAN")) return "border border-blue-500/20 bg-blue-500/10 text-blue-400"
        if (actionType.includes("CHAT") || actionType.includes("AI")) return "border border-violet-500/20 bg-violet-500/10 text-violet-400"
        if (actionType.includes("USER")) return "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
        return "border border-slate-500/20 bg-slate-500/10 text-slate-400"
    }

    const loadingRows = Array.from({ length: 6 }, (_, index) => index)

    return (
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 bg-slate-950 p-6 pb-20 text-slate-200">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight text-white">
                    SOC2 Audit Trail
                </h1>
                <p className="flex items-center gap-2 text-slate-400">
                    <ShieldCheck className="w-4 h-4" /> Immutable log of all critical cloud safety and AI platform interactions.
                </p>
            </div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <Card className="rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl">
                    <CardHeader>
                        <CardTitle className="text-white">Recent Activity</CardTitle>
                        <CardDescription className="text-slate-400">
                            Showing the last 50 compliance events.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {isLoading ? (
                            <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
                                <div className="grid grid-cols-[1.1fr_1fr_1fr_1.2fr] gap-4 border-b border-white/10 bg-white/5 px-4 py-3">
                                    {Array.from({ length: 4 }, (_, index) => (
                                        <Skeleton key={index} className="h-4 w-full bg-slate-800" />
                                    ))}
                                </div>

                                <div className="divide-y divide-white/5">
                                    {loadingRows.map((row) => (
                                        <div key={row} className="grid grid-cols-[1.1fr_1fr_1fr_1.2fr] gap-4 px-4 py-4">
                                            <Skeleton className="h-4 w-32 bg-slate-800" />
                                            <div className="flex items-center gap-2">
                                                <Skeleton className="h-8 w-8 rounded-lg bg-slate-800" />
                                                <Skeleton className="h-6 w-28 rounded-full bg-slate-800" />
                                            </div>
                                            <Skeleton className="h-4 w-40 bg-slate-800" />
                                            <Skeleton className="h-4 w-full bg-slate-800" />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
                                <Table>
                                    <TableHeader>
                                        <TableRow className="border-b border-white/5 bg-white/5 hover:bg-transparent">
                                            <TableHead className="px-4 py-3 text-xs uppercase tracking-wider text-slate-400">Timestamp</TableHead>
                                            <TableHead className="px-4 py-3 text-xs uppercase tracking-wider text-slate-400">Action</TableHead>
                                            <TableHead className="px-4 py-3 text-xs uppercase tracking-wider text-slate-400">Target</TableHead>
                                            <TableHead className="hidden px-4 py-3 text-xs uppercase tracking-wider text-slate-400 md:table-cell">Metadata</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {logs.length > 0 ? (
                                            logs.map((log) => (
                                                <TableRow key={log.id} className="border-b border-white/5 transition-colors hover:bg-white/[0.03]">
                                                    <TableCell className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">
                                                        {format(new Date(log.created_at), "MMM d, yyyy HH:mm:ss")}
                                                    </TableCell>
                                                    <TableCell className="px-4 py-3 text-slate-300">
                                                        <div className="flex items-center gap-2">
                                                            {getActionIcon(log.action_type)}
                                                            <Badge variant="outline" className={`rounded-full px-2.5 py-1 text-xs font-medium ${getActionColor(log.action_type)}`}>
                                                                {log.action_type.replace(/_/g, " ")}
                                                            </Badge>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="px-4 py-3 text-sm font-medium text-slate-300">
                                                        {log.resource_target}
                                                    </TableCell>
                                                    <TableCell className="hidden max-w-xs truncate px-4 py-3 text-xs text-slate-400 md:table-cell">
                                                        {JSON.stringify(log.metadata)}
                                                    </TableCell>
                                                </TableRow>
                                            ))
                                        ) : (
                                            <TableRow>
                                                <TableCell colSpan={4} className="h-24 px-4 py-3 text-center text-slate-400">
                                                    No audit logs found.
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    )
}
