"use client";

import { ShieldCheck } from "lucide-react";
import { CommitmentEmptyState } from "./empty-state";

export function CoverageDonut() {
    return <CommitmentEmptyState icon={ShieldCheck} title="Coverage: Not measured" subtitle="No measured coverage in this snapshot." />;
}
