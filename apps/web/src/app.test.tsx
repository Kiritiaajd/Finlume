import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PREFERENCES_STORAGE_KEY } from "@/lib/preferences";
import { jsonResponse, mockFetch, renderApp } from "@/test/utils";

// Canvas rendering is not available in jsdom; the chart wrapper is replaced
// by a placeholder that keeps its accessible label.
vi.mock("@/components/charts/EChart", () => ({
  EChart: ({ ariaLabel }: { ariaLabel: string }) => <div role="img" aria-label={ariaLabel} />,
}));

afterEach(() => vi.unstubAllGlobals());

const healthy = () =>
  mockFetch(async () => jsonResponse({ status: "ok", checks: { database: "ok" } }));

describe("application shell", () => {
  it("links to every section", async () => {
    healthy();
    renderApp();

    const nav = screen.getAllByRole("navigation", { name: "Main" })[0]!;
    for (const name of ["Dashboard", "Financial statements", "Analysis", "Reports", "Settings"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
  });

  it("shows an honest empty state on the dashboard by default", async () => {
    healthy();
    renderApp();

    expect(screen.getByRole("heading", { name: "No financial data yet" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add a statement" })).toBeDisabled();
    expect(await screen.findByText("Connected to the Finlume API")).toBeInTheDocument();
  });

  it("explains when the API is unavailable", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    renderApp();

    expect(await screen.findByText("The Finlume API is unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("API unavailable").length).toBeGreaterThan(0);
  });

  it("labels the sample dashboard as synthetic", async () => {
    healthy();
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("tab", { name: /sample dashboard/i }));

    expect(await screen.findByText("Synthetic sample data")).toBeInTheDocument();
    expect(screen.getByText("Sample Company (fictional)")).toBeInTheDocument();
    expect(screen.getAllByRole("img").length).toBeGreaterThanOrEqual(2);
  });

  it.each([
    ["/statements", "Financial statements", "Import CSV"],
    ["/analysis", "Analysis", "Run analysis"],
    ["/reports", "Reports", "New report"],
  ])("%s shows its page with unavailable actions disabled", async (path, title, action) => {
    healthy();
    renderApp(path);

    expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: action })).toBeDisabled();
  });

  it("shows a not-found page for unknown routes", () => {
    healthy();
    renderApp("/nope");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

describe("settings", () => {
  it("saves display preferences in this browser", async () => {
    healthy();
    const user = userEvent.setup();
    renderApp("/settings");

    await user.selectOptions(screen.getByLabelText("Show ratios as"), "decimal");
    await user.selectOptions(screen.getByLabelText("Theme"), "dark");
    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(await screen.findByText("Saved in this browser")).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PREFERENCES_STORAGE_KEY)!)).toEqual({
      locale: "en-US",
      theme: "dark",
      ratioDisplay: "decimal",
    });
    expect(document.documentElement).toHaveClass("dark");
  });
});
