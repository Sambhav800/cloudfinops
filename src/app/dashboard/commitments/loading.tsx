import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div aria-label="Loading commitments" className="space-y-6 p-6">
      <Skeleton className="h-10 w-64 bg-slate-800" />
      <Skeleton className="h-40 w-full rounded-2xl bg-slate-800" />
      <Skeleton className="h-60 w-full rounded-2xl bg-slate-800" />
    </div>
  );
}
