
import { describe, expect, it } from "vitest";
import { normalizeMatchResponse } from "./match";

describe("Real FastAPI response normalization", () => {
  it("reads flat vehicle fields and checks", () => {
    const response = {
      count: 1,
      candidates: [
        {
          vehicle_id: 88,
          title: "2019 Toyota C-HR",
          price_cash: "23388",
          year: 2019,
          mileage_km: 58901,
          body_style: "SUV",
          drivetrain: "FWD",
          checks: [
            {
              field: "budget",
              status: "met",
              requested: "30000",
              actual: "23388",
              difference: null,
              explanation: "Within budget limit.",
            },
            {
              field: "model",
              status: "not_met",
              requested: "RAV4",
              actual: "2019 Toyota C-HR",
              difference: null,
              explanation: "Model does not match.",
            },
            {
              field: "min_year",
              status: "not_met",
              requested: 2020,
              actual: 2019,
              difference: 1,
              explanation: "Vehicle is 1 model year older.",
            },
          ],
        },
      ],
      message: null,
    };

    const results = normalizeMatchResponse(response);

    expect(results).toHaveLength(1);
    expect(results[0].id).toBe(88);
    expect(results[0].vehicle.price_cash).toBe("23388");

    expect(results[0].conditions).toHaveLength(3);
    expect(results[0].conditions[0].status).toBe("met");
    expect(results[0].conditions[1].status).toBe("not_met");
    expect(results[0].conditions[2].difference).toBe(1);
    expect(results[0].conditions[2].requested).toBe(2020);
  });
});
