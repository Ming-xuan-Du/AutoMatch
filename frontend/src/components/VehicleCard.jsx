import { useState } from "react";

const moneyFormatter = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("en-CA");

const conditionLabels = {
  max_budget: "Cash budget",
  budget: "Cash budget",
  make: "Make",
  model: "Model",
  min_year: "Minimum year",
  year: "Minimum year",
  max_mileage_km: "Maximum mileage",
  mileage: "Maximum mileage",
  body_style: "Body style",
  drivetrain: "Drivetrain",
};

function displayValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function safeHttpUrl(value) {
  if (!value || typeof value !== "string") {
    return null;
  }

  try {
    const url = new URL(value);

    if (url.protocol !== "https:" && url.protocol !== "http:") {
      return null;
    }

    return url.href;
  } catch {
    return null;
  }
}

function formatDifference(condition) {
  const difference = condition.difference;

  if (difference === null || difference === undefined) {
    return null;
  }

  if (typeof difference !== "number") {
    return displayValue(difference);
  }

  const field = String(condition.field ?? "").toLowerCase();

  let unit = "";

  if (field.includes("mileage")) {
    unit = " km";
  } else if (field.includes("budget") || field.includes("price")) {
    unit = " CAD";
  } else if (field.includes("year")) {
    unit = " years";
  }

  return numberFormatter.format(difference) + unit;
}

function ConditionItem({ condition }) {
  const status = condition.status;

  const statusLabels = {
    met: "Met",
    not_met: "Not met",
    unknown: "Unknown",
    unavailable: "Status unavailable",
  };

  const label =
    conditionLabels[condition.field] ??
    String(condition.field || "Condition").replaceAll("_", " ");

  const difference = formatDifference(condition);

  return (
    <li className="condition-item">
      <div className="condition-heading">
        <strong>{label}</strong>

        <span className={`condition-status status-${status}`}>
          {statusLabels[status] ?? "Status unavailable"}
        </span>
      </div>

      {condition.explanation != null && (
        <p>{displayValue(condition.explanation)}</p>
      )}

      {(condition.requested != null ||
        condition.actual != null) && (
        <p className="condition-details">
          Requested: {displayValue(condition.requested)}
          {" · "}
          Vehicle: {displayValue(condition.actual)}
        </p>
      )}

      {difference !== null && (
        <p className="condition-difference">
          Difference: {difference}
        </p>
      )}
    </li>
  );
}

export default function VehicleCard({ match }) {
  const { vehicle, conditions } = match;
  const [imageFailed, setImageFailed] = useState(false);

  const imageUrl = safeHttpUrl(vehicle.image_url);
  const listingUrl = safeHttpUrl(vehicle.listing_url);

  const title =
    vehicle.title ||
    [vehicle.year, vehicle.make, vehicle.model]
      .filter(Boolean)
      .join(" ") ||
    "Untitled vehicle";

  const cashPrice =
    vehicle.price_cash === null ||
    vehicle.price_cash === undefined
      ? null
      : Number(vehicle.price_cash);

  const validCashPrice =
    cashPrice !== null && Number.isFinite(cashPrice);

  return (
    <article className="vehicle-card">
      <div className="vehicle-image">
        {imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt={title}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="image-fallback">
            <span>No vehicle image available</span>
          </div>
        )}
      </div>

      <div className="vehicle-content">
        <h3>{title}</h3>

        <div className="vehicle-price">
          {validCashPrice
            ? moneyFormatter.format(cashPrice)
            : "Cash price unavailable"}
        </div>

        <div className="vehicle-specs">
          <div>
            <span>Year</span>
            <strong>{displayValue(vehicle.year)}</strong>
          </div>

          <div>
            <span>Mileage</span>
            <strong>
              {vehicle.mileage_km != null
                ? `${numberFormatter.format(vehicle.mileage_km)} km`
                : "Unavailable"}
            </strong>
          </div>

          <div>
            <span>Body style</span>
            <strong>{displayValue(vehicle.body_style)}</strong>
          </div>

          <div>
            <span>Drivetrain</span>
            <strong>{displayValue(vehicle.drivetrain)}</strong>
          </div>
        </div>

        <div className="match-explanations">
          <h4>Requirement comparison</h4>

          {conditions.length > 0 ? (
            <ul>
              {conditions.map((condition, index) => (
                <ConditionItem
                  key={`${condition.field}-${index}`}
                  condition={condition}
                />
              ))}
            </ul>
          ) : (
            <p className="missing-explanations">
              Matching explanations were not found in the
              API response.
            </p>
          )}
        </div>

        {listingUrl ? (
          <a
            className="listing-link"
            href={listingUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            View original listing
          </a>
        ) : (
          <p className="listing-unavailable">
            Original listing link unavailable
          </p>
        )}
      </div>
    </article>
  );
}