import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("/api/health")) {
        return { ok: true, json: async () => ({ application: "available", model_ready: true, inference_ready: false }) } as Response;
      }
      if (String(url).includes("/api/model/info")) {
        return { ok: true, json: async () => ({ model_version: "V4", inference_production_ready: false }) } as Response;
      }
      return { ok: false, json: async () => ({}) } as Response;
    })
  );
});

describe("App", () => {
  it("renders Layer 0 notice", async () => {
    render(<App />);
    expect(screen.getByText(/Layer 0/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Health/i)).toBeInTheDocument());
  });
});
