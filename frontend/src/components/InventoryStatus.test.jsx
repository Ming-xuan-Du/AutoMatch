import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  cleanup,
  render,
  screen,
} from "@testing-library/react";

import InventoryStatus from "./InventoryStatus";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("InventoryStatus", () => {
  it("displays real inventory status fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        confirmed_present_count: 219,
        latest_snapshot: {
          id: 6,
          status: "success",
          pages_expected: 1,
          pages_seen: 1,
          scraped_at: "2026-11-02T17:04:34-05:00",
        },
        last_successful_snapshot: {
          id: 6,
          status: "success",
          scraped_at: "2026-11-02T17:04:34-05:00",
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryStatus />);

    expect(
      await screen.findByText("219")
    ).toBeInTheDocument();

    expect(
      screen.getByText("SUCCESS")
    ).toBeInTheDocument();

    expect(
      screen.getByText("1 of 1 pages recorded")
    ).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/inventory/status",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      })
    );
  });

  it("displays an API error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
      })
    );

    render(<InventoryStatus />);

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Inventory status request failed (500)"
    );
  });

  it("handles missing snapshot history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          confirmed_present_count: 0,
          latest_snapshot: null,
          last_successful_snapshot: null,
        }),
      })
    );

    render(<InventoryStatus />);

    expect(
      await screen.findByText("Not recorded")
    ).toBeInTheDocument();

    expect(
      screen.getByText("No snapshot recorded")
    ).toBeInTheDocument();
  });
});
