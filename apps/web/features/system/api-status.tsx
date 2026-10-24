"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, CircleDashed, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { API_BASE_URL } from "@/lib/config";

type CheckStatus = "ok" | "error" | "not_configured";
type Readiness = {
  status: "ok" | "degraded";
  checks: Record<string, { status: CheckStatus }>;
};

export async function fetchReadiness(): Promise<Readiness> {
  // 503 responses still carry a readable body describing which dependency failed.
  const res = await fetch(`${API_BASE_URL}/health/ready`, { cache: "no-store" });
  if (res.status !== 200 && res.status !== 503) {
    throw new Error(`Unexpected response (${res.status})`);
  }
  return (await res.json()) as Readiness;
}

const LABELS: Record<string, string> = { database: "Database", redis: "Redis" };

function CheckIcon({ status }: { status: CheckStatus }) {
  if (status === "ok") return <CircleCheck className="size-4 text-success" aria-hidden />;
  if (status === "error") return <CircleAlert className="size-4 text-destructive" aria-hidden />;
  return <CircleDashed className="size-4 text-muted-foreground" aria-hidden />;
}

export function ApiStatus() {
  const { data, error, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["health", "ready"],
    queryFn: fetchReadiness,
    retry: false,
  });

  if (isLoading) {
    return (
      <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Checking API…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div role="alert" className="space-y-2 text-sm">
        <p className="flex items-center gap-2 text-destructive">
          <CircleAlert className="size-4" aria-hidden /> API unreachable
        </p>
        <p className="text-muted-foreground">
          Could not reach {API_BASE_URL}. Start the backend (see README) and retry.
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="text-primary underline-offset-4 hover:underline disabled:opacity-50"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm" data-testid="api-status">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">API status</span>
        <Badge variant={data.status === "ok" ? "secondary" : "destructive"}>{data.status}</Badge>
      </div>
      <ul className="space-y-1.5">
        {Object.entries(data.checks).map(([name, check]) => (
          <li key={name} className="flex items-center gap-2">
            <CheckIcon status={check.status} />
            <span>{LABELS[name] ?? name}</span>
            <span className="text-muted-foreground">{check.status.replace("_", " ")}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
