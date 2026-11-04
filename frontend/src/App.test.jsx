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
  default: () => null,
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

function submitToyotaSearch() {
  fireEvent.change(screen.getByLabelText("Make"), {
    target: { value: "Toyota" },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: /find matching vehicles/i,
    })
  );
}

describe("AutoMatch search interface", () => {
  it("submits customer requirements and displays a vehicle", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse({
        candidates: [
          {
            vehicle: {
              id: 10,
              title: "2020 Toyota Corolla",
              year: 2020,
              price_cash: 23500,
              mileage_km: 85000,
              body_style: "Sedan",
              drivetrain: "FWD",
              image_url: null,
              listing_url:
                "https://example.com/vehicles/10",
            },
            conditions: [
              {
                field: "make",
                status: "met",
                explanation: "Toyota matches Toyota",
              },
              {
                field: "max_mileage_km",
                status: "not_met",
                difference: 5000,
              },
              {
                field: "drivetrain",
                status: "unknown",
              },
            ],
          },
        ],
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.change(
      screen.getByLabelText("Maximum cash budget (CAD)"),
      { target: { value: "30000" } }
    );

    submitToyotaSearch();

    expect(
      await screen.findByText("2020 Toyota Corolla")
    ).toBeInTheDocument();

    expect(
      screen.getByText(/\$23,500/)
    ).toBeInTheDocument();

    expect(
        screen.getByText("Difference: 5,000 km")
    ).toBeInTheDocument();

    expect(screen.getByText("Met")).toBeInTheDocument();
    expect(screen.getByText("Not met")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: "View original listing",
      })
    ).toHaveAttribute(
      "href",
      "https://example.com/vehicles/10"
    );

    const sentPayload = JSON.parse(
      fetchMock.mock.calls[0][1].body
    );

    expect(sentPayload).toMatchObject({
      make: "Toyota",
      max_budget: 30000,
      model: null,
    });
  });

  it("shows the empty-result state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ candidates: [] })
      )
    );

    render(<App />);
    submitToyotaSearch();

    expect(
      await screen.findByText("No eligible vehicles found")
    ).toBeInTheDocument();
  });

  it("shows a backend error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(
          { detail: "Database connection failed" },
          500
        )
      )
    );

    render(<App />);
    submitToyotaSearch();

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent("Database connection failed");
  });

  it("rejects an empty requirements form", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /find matching vehicles/i,
      })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Enter at least one customer requirement."
    );

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not substitute financing price for cash price", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          candidates: [
            {
              vehicle: {
                id: 20,
                title: "2019 Toyota C-HR",
                year: 2019,
                price_cash: null,
                price_finance: 18900,
                mileage_km: null,
                image_url: null,
                listing_url: null,
              },
              conditions: [
                {
                  field: "max_budget",
                  status: "unknown",
                  explanation: "Cash price unavailable",
                },
              ],
            },
          ],
        })
      )
    );

    render(<App />);
    submitToyotaSearch();

    expect(
      await screen.findByText("2019 Toyota C-HR")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Cash price unavailable", {
        selector: ".vehicle-price",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText("No vehicle image available")
    ).toBeInTheDocument();

    expect(
      screen.queryByText(/\$18,900/)
    ).not.toBeInTheDocument();
  });

  it("reports an unrecognized backend response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ unexpected_field: [] })
      )
    );

    render(<App />);
    submitToyotaSearch();

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Unexpected matching API response"
    );
  });
});