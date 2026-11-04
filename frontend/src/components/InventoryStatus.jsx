
import { useEffect, useState } from "react";

function formatTimestamp(value) {
  if (!value) return "Unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }

  return date.toLocaleString();
}

export default function InventoryStatus() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadInventoryStatus() {
      try {
        const response = await fetch("/api/inventory/status", {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            `Inventory status request failed (${response.status}).`
          );
        }

        const result = await response.json();

        if (
          !result ||
          typeof result.confirmed_present_count !== "number"
        ) {
          throw new Error("Invalid inventory status response.");
        }

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message || "Unable to load inventory status.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadInventoryStatus();

    return () => controller.abort();
  }, []);

  return (
    <section className="inventory-status-panel">
      <div className="section-heading">
        <div>
          <span className="section-kicker">
            INVENTORY / OVERVIEW
          </span>
          <h2>Inventory status</h2>
          <p>Current inventory synchronization information.</p>
        </div>
      </div>

      {loading && (
        <p role="status">Loading inventory status...</p>
      )}

      {!loading && error && (
        <p role="alert">Inventory status unavailable: {error}</p>
      )}

      {!loading && !error && data && (
        <div className="inventory-status-grid">
          <div className="inventory-stat">
            <span>Confirmed-present vehicles</span>
            <strong>
              {data.confirmed_present_count.toLocaleString()}
            </strong>
            <small>
              Active vehicles with no outstanding missing streak
            </small>
          </div>

          <div className="inventory-stat">
            <span>Latest snapshot status</span>
            <strong>
              {data.latest_snapshot?.status
                ? data.latest_snapshot.status.toUpperCase()
                : "UNKNOWN"}
            </strong>
            <small>
              {data.latest_snapshot
                ? `${data.latest_snapshot.pages_seen} of ${data.latest_snapshot.pages_expected} pages recorded`
                : "No snapshot recorded"}
            </small>
          </div>

          <div className="inventory-stat">
            <span>Last successful snapshot</span>
            <strong className="inventory-timestamp">
              {data.last_successful_snapshot
                ? formatTimestamp(
                    data.last_successful_snapshot.scraped_at
                  )
                : "Not recorded"}
            </strong>
            <small>Source inventory scrape time</small>
          </div>
        </div>
      )}
    </section>
  );
}
