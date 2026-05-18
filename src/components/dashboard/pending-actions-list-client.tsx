"use client";

import type { ActionItem } from "@/lib/dashboard/data";
import { ErrorBanner } from "@/components/dashboard/error-banner";
import { PendingActionsList } from "@/components/dashboard/actions-list";

export function PendingActionsListClient({ initialActions, loadError }: { initialActions: ActionItem[]; loadError: string | null }) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <PendingActionsList initialActions={initialActions} />
        </div>
    );
}
