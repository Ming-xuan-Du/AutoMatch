import { useEffect, useRef, useState } from "react";

import {
  fetchAnomalies,
  fetchAnomalyDetail,
  saveAnomalyReview,
} from "../api/anomalies";

const PAGE_SIZE = 10;

const STATUS_LABELS = {
  pending: "Pending",
  valid_issue: "Valid issue",
  false_alarm: "False alarm",
};

function formatDate(value) {
  if (!value) return "Unavailable";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Unavailable"
    : date.toLocaleString();
}

function safeListingUrl(value) {
  if (!value) return null;

  try {
    const url = new URL(value);

    return ["https:", "http:"].includes(url.protocol)
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export default function AnomalyReview() {
  const [apiKey, setApiKey] = useState("");
  const [connected, setConnected] = useState(false);

  const [reviewStatus, setReviewStatus] =
    useState("pending");
  const [detector, setDetector] = useState("all");
  const [offset, setOffset] = useState(0);

  const [list, setList] = useState(null);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] =
    useState(false);
  const [detailError, setDetailError] = useState("");

  const [decision, setDecision] = useState("pending");
  const [note, setNote] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [notice, setNotice] = useState("");

  const [listVersion, setListVersion] = useState(0);
  const [detailVersion, setDetailVersion] =
    useState(0);

  const detailRef = useRef(null);

  // Load the review queue only after a key is provided.
  useEffect(() => {
    if (!connected) return;

    const controller = new AbortController();

    setListLoading(true);
    setListError("");

    fetchAnomalies({
      apiKey,
      reviewStatus,
      detector,
      offset,
      limit: PAGE_SIZE,
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted) {
          setList(result);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setList(null);
          setListError(error.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setListLoading(false);
        }
      });

    return () => controller.abort();
  }, [
    connected,
    apiKey,
    reviewStatus,
    detector,
    offset,
    listVersion,
  ]);

  // Fetch full evidence and history for one finding.
  useEffect(() => {
    if (!connected || selectedId === null) return;

    const controller = new AbortController();

    setDetail(null);
    setDetailError("");
    setDetailLoading(true);

    fetchAnomalyDetail(
      selectedId,
      apiKey,
      controller.signal
    )
      .then((result) => {
        if (controller.signal.aborted) return;

        setDetail(result);
        setDecision(result.review_status);
        setNote(result.reviewer_note ?? "");
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setDetailError(error.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setDetailLoading(false);
        }
      });

    return () => controller.abort();
  }, [connected, apiKey, selectedId, detailVersion]);

  function connect(event) {
    event.preventDefault();

    if (apiKey.trim().length < 32) {
      setListError(
        "Enter the configured review API key."
      );
      return;
    }

    setListError("");
    setNotice("");
    setConnected(true);
  }

  function disconnect() {
    setConnected(false);
    setApiKey("");
    setList(null);
    setSelectedId(null);
    setDetail(null);
    setListError("");
    setDetailError("");
    setSaveError("");
    setNotice("");
  }

  function changeStatus(event) {
    setReviewStatus(event.target.value);
    setOffset(0);
    setSelectedId(null);
    setDetail(null);
  }

  function changeDetector(event) {
    setDetector(event.target.value);
    setOffset(0);
    setSelectedId(null);
    setDetail(null);
  }

  useEffect(() => {
  if (selectedId !== null) {
    detailRef.current?.scrollIntoView?.({
      behavior: "smooth",
      block: "start",
    });
  }
}, [selectedId]);

  function openFinding(id) {
    setSelectedId(id);
    setDetail(null);
    setSaveError("");
    setNotice("");
  }

  async function handleSave(event) {
    event.preventDefault();

    if (!detail || saving) return;

    setSaveError("");
    setNotice("");
    setSaving(true);

    try {
      const result = await saveAnomalyReview(
        detail.id,
        apiKey,
        {
          review_status: decision,
          reviewer_note: note.trim() || null,
        }
      );

      setNotice(
        result.changed
          ? "Review saved successfully."
          : "No review changes were necessary."
      );

      // Refresh the filtered queue.
      setListVersion((value) => value + 1);

      if (
        reviewStatus !== "all" &&
        decision !== reviewStatus
      ) {
        // The finding no longer belongs to this filter.
        setSelectedId(null);
        setDetail(null);
      } else {
        // Reload the finding and its audit history.
        setDetailVersion((value) => value + 1);
      }
    } catch (error) {
      setSaveError(error.message);
    } finally {
      setSaving(false);
    }
  }

  // Keep development-only review controls out of public builds.
  // This is a UI restriction, not an authentication mechanism.
  if (
    import.meta.env.PROD ||
    import.meta.env.VITE_AUTOMATCH_PUBLIC_DEMO === "1"
  ) {
    return null;
  }

  return (
    <section
      className="anomaly-panel"
      aria-label="Anomaly review dashboard"
    >
      <div className="section-heading">
        <div>
          <span className="section-kicker">
            03 / DATA QUALITY
          </span>
          <h2>Anomaly review</h2>
          <p>
            Review potential inventory anomalies.
            Findings are not confirmed listing errors.
          </p>
        </div>

        {connected && (
          <button
            type="button"
            className="clear-button"
            onClick={disconnect}
          >
            Disconnect
          </button>
        )}
      </div>

      {!connected && (
        <form
          className="anomaly-key-form"
          onSubmit={connect}
        >
          <label htmlFor="anomaly-api-key">
            Review API key
          </label>

          <input
            id="anomaly-api-key"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(event) =>
              setApiKey(event.target.value)
            }
            placeholder="Enter your local review key"
          />

          <p className="anomaly-help">
            For local development only. Your key stays
            in this page's memory and is not saved to
            browser storage.
          </p>

          <button
            type="submit"
            className="search-button"
          >
            Connect to anomaly review
          </button>

          {listError && (
            <p role="alert" className="anomaly-error">
              {listError}
            </p>
          )}
        </form>
      )}

      {connected && (
        <>
          <div className="anomaly-toolbar">
            <div className="form-field">
              <label htmlFor="anomaly-status-filter">
                Review status filter
              </label>
              <select
                id="anomaly-status-filter"
                value={reviewStatus}
                onChange={changeStatus}
              >
                <option value="all">All statuses</option>
                <option value="pending">Pending</option>
                <option value="valid_issue">
                  Valid issues
                </option>
                <option value="false_alarm">
                  False alarms
                </option>
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="anomaly-detector-filter">
                Detector filter
              </label>
              <select
                id="anomaly-detector-filter"
                value={detector}
                onChange={changeDetector}
              >
                <option value="all">All detectors</option>
                <option value="rule">Rules</option>
                <option value="model">
                  Isolation Forest
                </option>
              </select>
            </div>

            <button
              type="button"
              className="clear-button"
              onClick={() =>
                setListVersion((value) => value + 1)
              }
              disabled={listLoading}
            >
              Refresh findings
            </button>
          </div>

          {notice && (
            <p role="status" className="anomaly-success">
              {notice}
            </p>
          )}

          {listLoading && (
            <p role="status">
              Loading anomaly findings...
            </p>
          )}

          {listError && (
            <p role="alert" className="anomaly-error">
              {listError}
            </p>
          )}

          {!listLoading &&
            !listError &&
            list?.items.length === 0 && (
              <div className="message-panel">
                <strong>
                  No anomaly findings for this filter
                </strong>
                <p>
                  Try another review status or detector.
                </p>
              </div>
            )}

          {!listLoading &&
            !listError &&
            list &&
            list.items.length > 0 && (
              <>
                <p className="anomaly-count">
                  {list.total} findings match these filters
                </p>

                <div className="anomaly-list">
                  {list.items.map((finding) => (
                    <article
                      key={finding.id}
                      className="anomaly-item"
                    >
                      <div>
                        <h3>{finding.vehicle.title}</h3>

                        <p>{finding.explanation}</p>

                        <div className="anomaly-meta">
                          <span>
                            Finding #{finding.id}
                          </span>

                          <span>
                            {finding.detector === "model"
                              ? "Experimental ML"
                              : "Rule-based"}
                          </span>

                          <span>
                            {STATUS_LABELS[
                              finding.review_status
                            ]}
                          </span>
                        </div>

                        {finding.detector === "model" &&
                          finding.score != null && (
                            <p className="anomaly-help">
                              Decision score:{" "}
                              {Number(
                                finding.score
                              ).toFixed(4)}
                            </p>
                          )}
                      </div>

                      <button
                        type="button"
                        className="clear-button"
                        onClick={() =>
                          openFinding(finding.id)
                        }
                      >
                        Review finding {finding.id}
                      </button>
                    </article>
                  ))}
                </div>

                <div className="anomaly-pagination">
                  <button
                    type="button"
                    className="clear-button"
                    disabled={offset === 0 || listLoading}
                    onClick={() => {
                      setOffset(
                        Math.max(0, offset - PAGE_SIZE)
                      );
                      setSelectedId(null);
                      setDetail(null);
                    }}
                  >
                    Previous
                  </button>

                  <span>
                    Showing {offset + 1}–
                    {Math.min(
                      offset + PAGE_SIZE,
                      list.total
                    )}{" "}
                    of {list.total}
                  </span>

                  <button
                    type="button"
                    className="clear-button"
                    disabled={
                      offset + PAGE_SIZE >= list.total ||
                      listLoading
                    }
                    onClick={() => {
                      setOffset(offset + PAGE_SIZE);
                      setSelectedId(null);
                      setDetail(null);
                    }}
                  >
                    Next
                  </button>
                </div>
              </>
            )}

          {selectedId !== null && (
            <div
                ref={detailRef}
                className="anomaly-detail"
            >
              <div className="anomaly-detail-heading">
                <h3>
                  Finding #{selectedId} — Review details
                </h3>

                <button
                  type="button"
                  className="clear-button"
                  onClick={() => {
                    setSelectedId(null);
                    setDetail(null);
                    setSaveError("");
                  }}
                >
                  Close details
                </button>
              </div>

              {detailLoading && (
                <p role="status">
                  Loading finding details...
                </p>
              )}

              {detailError && (
                <p role="alert" className="anomaly-error">
                  {detailError}
                </p>
              )}

              {detail && !detailLoading && (
                <>
                  <h4>{detail.vehicle.title}</h4>

                  <div className="anomaly-meta">
                    <span>
                      {detail.vehicle.year ??
                        "Year unavailable"}
                    </span>
                    <span>
                      Cash price:{" "}
                      {detail.vehicle.price_cash == null
                        ? "Unavailable"
                        : `$${detail.vehicle.price_cash.toLocaleString()}`}
                    </span>
                    <span>
                      Mileage:{" "}
                      {detail.vehicle.mileage_km == null
                        ? "Unavailable"
                        : `${detail.vehicle.mileage_km.toLocaleString()} km`}
                    </span>
                  </div>

                  {safeListingUrl(
                    detail.vehicle.listing_url
                  ) && (
                    <a
                      className="anomaly-original-link"
                      href={safeListingUrl(
                        detail.vehicle.listing_url
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View original listing
                    </a>
                  )}

                  <p>
                    <strong>Issue:</strong>{" "}
                    {detail.explanation}
                  </p>

                  <p className="anomaly-help">
                    First detected:{" "}
                    {formatDate(
                      detail.first_detected_at
                    )}
                    {" | "}
                    Last detected:{" "}
                    {formatDate(
                      detail.last_detected_at
                    )}
                  </p>

                  <p className="anomaly-help">
                    Detection history does not prove
                    that a finding is still present in
                    the latest inventory.
                  </p>

                  {detail.detector === "model" && (
                    <div className="anomaly-ml-note">
                      <strong>
                        Experimental Isolation Forest
                      </strong>
                      <p>
                        Model version:{" "}
                        {detail.model_version ??
                          "Unavailable"}
                      </p>
                      <p>
                        Decision score:{" "}
                        {detail.score == null
                          ? "Unavailable"
                          : detail.score.toFixed(6)}
                      </p>
                      <p>
                        This score is not a probability
                        or a measure of error certainty.
                      </p>
                    </div>
                  )}

                  <details>
                    <summary>
                      Detection evidence (read-only)
                    </summary>

                    <pre className="anomaly-evidence">
                      {JSON.stringify(
                        detail.evidence,
                        null,
                        2
                      )}
                    </pre>
                  </details>

                  <form
                    className="anomaly-review-form"
                    onSubmit={handleSave}
                  >
                    <div className="form-field">
                      <label htmlFor="anomaly-decision">
                        Review decision
                      </label>

                      <select
                        id="anomaly-decision"
                        value={decision}
                        onChange={(event) =>
                          setDecision(
                            event.target.value
                          )
                        }
                        disabled={saving}
                      >
                        <option value="pending">
                          Pending
                        </option>
                        <option value="valid_issue">
                          Valid issue
                        </option>
                        <option value="false_alarm">
                          False alarm
                        </option>
                      </select>
                    </div>

                    <div className="form-field">
                      <label htmlFor="anomaly-note">
                        Reviewer note
                      </label>

                      <textarea
                        id="anomaly-note"
                        rows={3}
                        maxLength={2000}
                        value={note}
                        onChange={(event) =>
                          setNote(event.target.value)
                        }
                        disabled={saving}
                        placeholder="Document your verification"
                      />
                    </div>

                    {saveError && (
                      <p
                        role="alert"
                        className="anomaly-error"
                      >
                        {saveError}
                      </p>
                    )}

                    <button
                      type="submit"
                      className="search-button"
                      disabled={saving}
                    >
                      {saving
                        ? "Saving review..."
                        : "Save review"}
                    </button>
                  </form>

                  <div className="anomaly-history">
                    <h4>Review history</h4>

                    {detail.review_events.length === 0 ? (
                      <p>No review decisions recorded.</p>
                    ) : (
                      <ol>
                        {detail.review_events.map(
                          (event) => (
                            <li key={event.id}>
                              <strong>
                                {STATUS_LABELS[
                                  event.previous_status
                                ]}{" "}
                                →{" "}
                                {STATUS_LABELS[
                                  event.new_status
                                ]}
                              </strong>

                              <p>
                                {formatDate(
                                  event.changed_at
                                )}
                              </p>

                              {event.new_note && (
                                <p>
                                  Note: {event.new_note}
                                </p>
                              )}
                            </li>
                          )
                        )}
                      </ol>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
