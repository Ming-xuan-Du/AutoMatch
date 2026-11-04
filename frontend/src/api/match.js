const FIELDS = [
  "max_budget",
  "make",
  "model",
  "min_year",
  "max_mileage_km",
  "body_style",
  "drivetrain",
];

const NUMERIC_FIELDS = new Set([
  "max_budget",
  "min_year",
  "max_mileage_km",
]);

const VALID_STATUSES = new Set([
  "met",
  "not_met",
  "unknown",
]);

export function buildMatchPayload(form) {
  const payload = {};

  for (const field of FIELDS) {
    const raw = String(form[field] ?? "").trim();

    if (!raw) {
      payload[field] = null;
      continue;
    }

    if (NUMERIC_FIELDS.has(field)) {
      const number = Number(raw);

      if (
        !Number.isFinite(number) ||
        !Number.isInteger(number) ||
        number < 0
      ) {
        throw new Error(
          `${field} must be a valid non-negative integer.`
        );
      }

      payload[field] = number;
    } else {
      payload[field] = raw;
    }
  }

  if (Object.values(payload).every((value) => value === null)) {
    throw new Error(
      "Enter at least one customer requirement."
    );
  }

  return payload;
}

function normalizeCondition(value, fallbackField = "") {
  let condition;

  if (value !== null && typeof value === "object") {
    condition = value;
  } else if (
    typeof value === "string" &&
    VALID_STATUSES.has(value)
  ) {
    condition = { status: value };
  } else {
    condition = { explanation: value };
  }

  const rawStatus =
    condition.status ??
    condition.result ??
    condition.outcome ??
    condition.met;

  let status = "unavailable";

  if (VALID_STATUSES.has(rawStatus)) {
    status = rawStatus;
  } else if (rawStatus === true) {
    status = "met";
  } else if (rawStatus === false) {
    status = "not_met";
  }

  return {
    field:
      condition.field ??
      condition.condition ??
      condition.requirement_name ??
      fallbackField,

    status,

    explanation:
      condition.explanation ??
      condition.reason ??
      condition.message ??
      condition.detail ??
      null,

    requested:
      condition.requested ??
      condition.expected ??
      condition.requested_value ??
      null,

    actual:
      condition.actual ??
      condition.actual_value ??
      condition.vehicle_value ??
      null,

    difference:
      condition.difference ??
      condition.delta ??
      condition.numeric_difference ??
      condition.difference_km ??
      condition.difference_amount ??
      null,
  };
}



function normalizeConditions(candidate) {
  const raw =
    candidate.checks ??
    candidate.condition_results ??
    candidate.conditions ??
    candidate.explanations ??
    candidate.match_explanations ??
    candidate.match_details ??
    candidate.criteria ??
    candidate.evaluations ??
    [];

  if (Array.isArray(raw)) {
    return raw.map((condition) =>
      normalizeCondition(condition)
    );
  }

  if (raw !== null && typeof raw === "object") {
    return Object.entries(raw).map(([field, value]) =>
      normalizeCondition(value, field)
    );
  }

  return [];
}


export function normalizeMatchResponse(body) {
  const candidates = Array.isArray(body)
    ? body
    : [
        body?.candidates,
        body?.matches,
        body?.results,
        body?.vehicles,
        body?.matched_vehicles,
      ].find(Array.isArray);

  if (!Array.isArray(candidates)) {
    throw new Error(
      "Unexpected matching API response. " +
      "Check backend/matching/schemas.py and " +
      "update the response adapter."
    );
  }

  // Preserve backend order. Never sort or rank candidates.
  return candidates.slice(0, 5).map((candidate, index) => {
    const vehicle =
      candidate.vehicle ??
      candidate.vehicle_details ??
      candidate.vehicle_data ??
      candidate;

    return {
        id:
            vehicle.id ??
            vehicle.vehicle_id ??
            candidate.vehicle_id ??
            vehicle.source_listing_id ??
            index,

      vehicle,
      conditions: normalizeConditions(candidate),
    };
  });
}

function getErrorMessage(body, status) {
  if (typeof body?.detail === "string") {
    return body.detail;
  }

  if (Array.isArray(body?.detail)) {
    return body.detail
      .map((error) => error.msg ?? "Invalid input")
      .join("; ");
  }

  return `Matching request failed (HTTP ${status}).`;
}

export async function fetchMatches(payload) {
  let response;

  try {
    response = await fetch("/api/vehicles/match", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "Cannot connect to the matching API. " +
      "Check that FastAPI is running on port 8000."
    );
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(body, response.status));
  }

  return normalizeMatchResponse(body);
}