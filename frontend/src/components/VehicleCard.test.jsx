
import { afterEach, describe, expect, it } from "vitest";
import {
  cleanup,
  render,
  screen,
} from "@testing-library/react";

import VehicleCard from "./VehicleCard";

afterEach(() => {
  cleanup();
});

const baseVehicle = {
  id: 1,
  source_listing_id: "DEMO-0001",
  title: "2020 Toyota RAV4 (Synthetic Demo)",
  year: 2020,
  price_cash: 24900,
  mileage_km: 93000,
  body_style: "SUV",
  drivetrain: "AWD",
  image_url: null,
  listing_url:
    "https://example.invalid/automatch/demo-0001",
};

function createMatch(vehicle) {
  return {
    id: vehicle.id,
    vehicle,
    conditions: [],
  };
}

describe("AutoMatch vehicle listing links", () => {
  it("does not link to synthetic demo inventory", () => {
    render(
      <VehicleCard
        match={createMatch(baseVehicle)}
      />
    );

    expect(
      screen.getByText(
        "Synthetic demo vehicle — not available for purchase."
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("link", {
        name: "View original listing",
      })
    ).not.toBeInTheDocument();
  });

  it("keeps real inventory listing links", () => {
    const realVehicle = {
      ...baseVehicle,
      source_listing_id: "REAL-001",
      title: "2020 Toyota RAV4",
      listing_url:
        "https://example.com/vehicles/real-001",
    };

    render(
      <VehicleCard
        match={createMatch(realVehicle)}
      />
    );

    expect(
      screen.getByRole("link", {
        name: "View original listing",
      })
    ).toHaveAttribute(
      "href",
      "https://example.com/vehicles/real-001"
    );

    expect(
      screen.queryByText(
        "Synthetic demo vehicle — not available for purchase."
      )
    ).not.toBeInTheDocument();
  });

  it("also blocks synthetic URLs without a demo ID", () => {
    const vehicle = {
      ...baseVehicle,
      source_listing_id: "OTHER-001",
    };

    render(
      <VehicleCard
        match={createMatch(vehicle)}
      />
    );

    expect(
      screen.queryByRole("link", {
        name: "View original listing",
      })
    ).not.toBeInTheDocument();
  });
});
