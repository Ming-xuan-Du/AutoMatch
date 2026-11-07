
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

import AnomalyReview from "./AnomalyReview";

import {
  fetchAnomalies,
  fetchAnomalyDetail,
  saveAnomalyReview,
} from "../api/anomalies";

vi.mock("../api/anomalies", () => ({
  fetchAnomalies: vi.fn(),
  fetchAnomalyDetail: vi.fn(),
  saveAnomalyReview: vi.fn(),
}));

const TEST_KEY = "a".repeat(36);

const finding = {
  id: 11,
  vehicle_id: 50,
  detector: "model",
  issue_type: "statistical_outlier",
  explanation: "Experimental statistical outlier",
  score: -0.151189,
  model_version: "iforest_v1",
  review_status: "pending",
  reviewer_note: null,
  first_detected_at: "2026-11-06T20:00:00Z",
  last_detected_at: "2026-11-06T20:00:00Z",
  evidence: {
    price_cash: 300000,
    mileage_km: 12000,
  },
  vehicle: {
    id: 50,
    title: "2012 Lamborghini Aventador SV KIT",
    year: 2012,
    price_cash: 300000,
    mileage_km: 12000,
    listing_url: "https://example.com/aventador",
  },
};

function connect() {
  fireEvent.change(
    screen.getByLabelText("Review API key"),
    {
      target: { value: TEST_KEY },
    }
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Connect to anomaly review",
    })
  );
}

beforeEach(() => {
  vi.resetAllMocks();

  fetchAnomalies.mockResolvedValue({
    total: 1,
    limit: 10,
    offset: 0,
    items: [finding],
  });

  fetchAnomalyDetail.mockResolvedValue({
    ...finding,
    review_events: [],
  });

  saveAnomalyReview.mockResolvedValue({
    changed: true,
    finding: {
      ...finding,
      review_status: "false_alarm",
    },
  });
});

afterEach(() => {
  cleanup();
});

describe("AutoMatch anomaly review dashboard", () => {
  it("does not request data before connection", () => {
    render(<AnomalyReview />);

    expect(
      screen.getByLabelText("Review API key")
    ).toBeInTheDocument();

    expect(fetchAnomalies).not.toHaveBeenCalled();
  });

  it("loads pending findings with the API key", async () => {
    render(<AnomalyReview />);
    connect();

    expect(
      await screen.findByText(
        "2012 Lamborghini Aventador SV KIT"
      )
    ).toBeInTheDocument();

    expect(fetchAnomalies).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: TEST_KEY,
        reviewStatus: "pending",
        detector: "all",
        offset: 0,
      })
    );

    expect(
      screen.getByText(
        "1 findings match these filters"
      )
    ).toBeInTheDocument();
  });

  it("updates detector and status filters", async () => {
    render(<AnomalyReview />);
    connect();

    await screen.findByText(
      "2012 Lamborghini Aventador SV KIT"
    );

    fireEvent.change(
      screen.getByLabelText("Detector filter"),
      {
        target: { value: "model" },
      }
    );

    fireEvent.change(
      screen.getByLabelText("Review status filter"),
      {
        target: { value: "false_alarm" },
      }
    );

    await waitFor(() => {
      expect(fetchAnomalies).toHaveBeenCalledWith(
        expect.objectContaining({
          detector: "model",
          reviewStatus: "false_alarm",
          offset: 0,
        })
      );
    });
  });

  it("shows evidence and human review controls", async () => {
    render(<AnomalyReview />);
    connect();

    await screen.findByText(
      "2012 Lamborghini Aventador SV KIT"
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Review finding 11",
      })
    );

    expect(
      await screen.findByLabelText("Review decision")
    ).toBeInTheDocument();

    expect(
      screen.getByText(/not a probability/i)
    ).toBeInTheDocument();

    expect(
      screen.getByText("Detection evidence (read-only)")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: "View original listing",
      })
    ).toHaveAttribute(
      "href",
      "https://example.com/aventador"
    );

    expect(fetchAnomalyDetail).toHaveBeenCalledWith(
      11,
      TEST_KEY,
      expect.anything()
    );
  });

  it("saves a review decision and reviewer note", async () => {
    render(<AnomalyReview />);
    connect();

    await screen.findByText(
      "2012 Lamborghini Aventador SV KIT"
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Review finding 11",
      })
    );

    await screen.findByLabelText("Review decision");

    fireEvent.change(
      screen.getByLabelText("Review decision"),
      {
        target: { value: "false_alarm" },
      }
    );

    fireEvent.change(
      screen.getByLabelText("Reviewer note"),
      {
        target: {
          value: "Verified with original listing",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Save review",
      })
    );

    await waitFor(() => {
      expect(saveAnomalyReview).toHaveBeenCalledWith(
        11,
        TEST_KEY,
        {
          review_status: "false_alarm",
          reviewer_note:
            "Verified with original listing",
        }
      );
    });

    expect(
      await screen.findByText(
        "Review saved successfully."
      )
    ).toBeInTheDocument();
  });

  it("shows an empty review queue", async () => {
    fetchAnomalies.mockResolvedValue({
      total: 0,
      limit: 10,
      offset: 0,
      items: [],
    });

    render(<AnomalyReview />);
    connect();

    expect(
      await screen.findByText(
        "No anomaly findings for this filter"
      )
    ).toBeInTheDocument();
  });

  it("shows API connection errors", async () => {
    fetchAnomalies.mockRejectedValue(
      new Error("Invalid review API key")
    );

    render(<AnomalyReview />);
    connect();

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent("Invalid review API key");
  });

  it("shows review update errors", async () => {
    saveAnomalyReview.mockRejectedValue(
      new Error("Review update failed")
    );

    render(<AnomalyReview />);
    connect();

    await screen.findByText(
      "2012 Lamborghini Aventador SV KIT"
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Review finding 11",
      })
    );

    await screen.findByLabelText("Review decision");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Save review",
      })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent("Review update failed");
  });
});
