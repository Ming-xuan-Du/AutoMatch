
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";

import App from "./App";

vi.mock("./components/InventoryStatus", () => ({
  default: () => <div>Inventory status mock</div>,
}));

vi.mock("./components/AnomalyReview", () => ({
  default: () => <div>Review dashboard mock</div>,
}));

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("AutoMatch public demo UI security", () => {
  it("preserves anomaly review in local development", () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_AUTOMATCH_PUBLIC_DEMO", "0");

    render(<App />);

    expect(
      screen.queryByText(
        "Portfolio Demo — Synthetic Inventory"
      )
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Open anomaly review",
      })
    );

    expect(
      screen.getByText("Review dashboard mock")
    ).toBeInTheDocument();
  });

  it("hides review controls in public demo mode", () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_AUTOMATCH_PUBLIC_DEMO", "1");

    render(<App />);

    expect(
      screen.getByText(
        "Portfolio Demo — Synthetic Inventory"
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "AI extraction unavailable in public demo",
      })
    ).toBeDisabled();

    expect(
      screen.queryByRole("button", {
        name: "Open anomaly review",
      })
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Review dashboard mock")
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("Customer requirements")
    ).toBeInTheDocument();
  });

  it("hides review controls in production by default", () => {
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_AUTOMATCH_PUBLIC_DEMO", "0");

    render(<App />);

    expect(
      screen.queryByRole("button", {
        name: "Open anomaly review",
      })
    ).not.toBeInTheDocument();
  });
});
