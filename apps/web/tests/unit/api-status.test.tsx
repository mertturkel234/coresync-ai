import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiStatus } from "@/features/system/api-status";

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApiStatus />
    </QueryClientProvider>,
  );
}

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status, ok: status < 400, json: async () => body }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("ApiStatus", () => {
  it("shows real dependency states from the readiness endpoint", async () => {
    mockFetch(200, {
      status: "ok",
      checks: { database: { status: "ok" }, redis: { status: "not_configured" } },
    });
    renderWithClient();
    expect(await screen.findByTestId("api-status")).toBeInTheDocument();
    expect(screen.getByText("Database")).toBeInTheDocument();
    expect(screen.getByText("not configured")).toBeInTheDocument();
  });

  it("renders a degraded state returned with HTTP 503", async () => {
    mockFetch(503, {
      status: "degraded",
      checks: { database: { status: "ok" }, redis: { status: "error" } },
    });
    renderWithClient();
    expect(await screen.findByText("degraded")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("shows an actionable error when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    renderWithClient();
    expect(await screen.findByRole("alert")).toHaveTextContent("API unreachable");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
