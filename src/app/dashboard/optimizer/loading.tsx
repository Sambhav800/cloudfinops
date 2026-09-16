import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div aria-label="Loading provider recommendations" className="space-y-6 p-6">
      <Skeleton className="h-10 w-64 bg-slate-800" />
      <Skeleton className="h-56 w-full rounded-2xl bg-slate-800" />
      <Skeleton className="h-80 w-full rounded-2xl bg-slate-800" />
    </div>
  );
}
