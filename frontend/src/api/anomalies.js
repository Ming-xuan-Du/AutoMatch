
const BASE_URL = "/api/anomalies";

function getErrorMessage(body, status) {
  if (typeof body?.detail === "string") {
    return body.detail;
  }

  if (Array.isArray(body?.detail)) {
    return body.detail
      .map((item) => item.msg ?? "Invalid input")
      .join("; ");
  }

  return `Anomaly API request failed (HTTP ${status}).`;
}

async function requestAnomalyAPI(
  path,
  apiKey,
  { method = "GET", body, signal } = {}
) {
  if (!apiKey || !apiKey.trim()) {
    throw new Error("Enter the review API key.");
  }

  let response;

  try {
    response = await fetch(path, {
      method,
      headers: {
        "X-AutoMatch-Review-Key": apiKey,
        ...(body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
      },
      ...(body !== undefined
        ? { body: JSON.stringify(body) }
        : {}),
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw error;
    }

    throw new Error(
      "Cannot connect to the anomaly API. " +
        "Check that FastAPI is running on port 8000."
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      getErrorMessage(data, response.status)
    );
  }

  return data;
}

export async function fetchAnomalies({
  apiKey,
  reviewStatus = "pending",
  detector = "all",
  offset = 0,
  limit = 10,
  signal,
}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (reviewStatus !== "all") {
    params.set("review_status", reviewStatus);
  }

  if (detector !== "all") {
    params.set("detector", detector);
  }

  const data = await requestAnomalyAPI(
    `${BASE_URL}?${params.toString()}`,
    apiKey,
    { signal }
  );

  if (
    !data ||
    !Array.isArray(data.items) ||
    !Number.isInteger(data.total) ||
    data.total < 0
  ) {
    throw new Error("Unexpected anomaly list response.");
  }

  return data;
}

export async function fetchAnomalyDetail(
  id,
  apiKey,
  signal
) {
  const data = await requestAnomalyAPI(
    `${BASE_URL}/${encodeURIComponent(id)}`,
    apiKey,
    { signal }
  );

  if (
    !data ||
    !data.vehicle ||
    !Array.isArray(data.review_events)
  ) {
    throw new Error("Unexpected anomaly detail response.");
  }

  return data;
}

export async function saveAnomalyReview(
  id,
  apiKey,
  payload
) {
  const data = await requestAnomalyAPI(
    `${BASE_URL}/${encodeURIComponent(id)}/review`,
    apiKey,
    {
      method: "PATCH",
      body: payload,
    }
  );

  if (!data || typeof data.changed !== "boolean") {
    throw new Error("Unexpected review update response.");
  }

  return data;
}
