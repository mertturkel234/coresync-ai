import { ApiStatus } from "@/features/system/api-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-8 px-6 py-16">
      <div className="space-y-3">
        <p className="font-mono text-xs uppercase tracking-widest text-primary">CoreSync AI</p>
        <h1 className="text-3xl font-semibold tracking-tight">
          Autonomous Intelligence for B2B Integration
        </h1>
        <p className="max-w-xl text-muted-foreground">
          Guide technical customers from API documentation to a verified integration result.
        </p>
      </div>
      <section aria-label="Platform status" className="rounded-xl border bg-card p-5">
        <ApiStatus />
      </section>
    </main>
  );
}
