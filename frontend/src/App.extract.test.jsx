import {
  afterEach,
  beforeEach,
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
  waitFor,
} from "@testing-library/react";

import App from "./App";
import { extractRequirements } from "./api/extract";
import { fetchMatches } from "./api/match";

vi.mock("./api/extract", () => ({
  extractRequirements: vi.fn(),
}));

vi.mock("./api/match", () => ({
  buildMatchPayload: (form) => form,
  fetchMatches: vi.fn(),
}));

vi.mock("./components/InventoryStatus", () => ({
  default: () => <div>Inventory status</div>,
}));

vi.mock("./components/VehicleCard", () => ({
  default: () => <div>Vehicle card</div>,
}));

const extractedResponse = {
  requirements: {
    max_budget: 30000,
    make: "Toyota",
    model: null,
    min_year: 2020,
    max_mileage_km: null,
    body_style: "SUV",
    drivetrain: "AWD",
  },
  field_states: {
    max_budget: "explicit",
    make: "explicit",
    model: "missing",
    min_year: "explicit",
    max_mileage_km: "missing",
    body_style: "explicit",
    drivetrain: "explicit",
  },
  evidence: {
    max_budget: "under 30000 CAD",
    make: "Toyota",
    model: null,
    min_year: "2020 or newer",
    max_mileage_km: null,
    body_style: "SUV",
    drivetrain: "AWD",
  },
  review_notes: [],
};

afterEach(() => {
  cleanup();
});

describe("AI requirement extraction UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMatches.mockResolvedValue([]);
  });

  it("fills editable fields without searching automatically", async () => {
    extractRequirements.mockResolvedValue(
      extractedResponse
    );

    render(<App />);

    fireEvent.change(
      screen.getByLabelText(
        "Natural-language customer requirements"
      ),
      {
        target: {
          value:
            "I need a Toyota SUV under 30000 CAD, " +
            "2020 or newer, with AWD.",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Extract requirements with AI",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByLabelText("Make").value
      ).toBe("Toyota");
    });

    expect(
        screen.getByLabelText("Minimum year").value
    ).toBe("2020");

    expect(fetchMatches).not.toHaveBeenCalled();
  });

  it("allows editing before calling the matcher", async () => {
    extractRequirements.mockResolvedValue(
      extractedResponse
    );

    render(<App />);

    fireEvent.change(
      screen.getByLabelText(
        "Natural-language customer requirements"
      ),
      {
        target: {
          value: "I need a Toyota SUV with AWD.",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Extract requirements with AI",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByLabelText("Make").value
      ).toBe("Toyota");
    });

    expect(fetchMatches).not.toHaveBeenCalled();

    fireEvent.change(
      screen.getByLabelText("Make"),
      { target: { value: "Honda" } }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Find matching vehicles",
      })
    );

    await waitFor(() => {
      expect(fetchMatches).toHaveBeenCalledWith(
        expect.objectContaining({
          make: "Honda",
        })
      );
    });
  });

  it("keeps the manual form available on failure", async () => {
    extractRequirements.mockRejectedValue(
      new Error("Local Ollama unavailable")
    );

    render(<App />);

    fireEvent.change(
      screen.getByLabelText(
        "Natural-language customer requirements"
      ),
      {
        target: {
          value: "I need a Toyota SUV.",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Extract requirements with AI",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByRole("alert").textContent
      ).toContain("Local Ollama unavailable");
    });

    expect(
      screen.getByLabelText("Make").value
    ).toBe("");

    expect(fetchMatches).not.toHaveBeenCalled();
  });
});
