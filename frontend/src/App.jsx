import InventoryStatus from "./components/InventoryStatus";
import { extractRequirements } from "./api/extract";
import AnomalyReview from "./components/AnomalyReview";
import { useState } from "react";
import VehicleCard from "./components/VehicleCard";
import {
  buildMatchPayload,
  fetchMatches,
} from "./api/match";

const initialForm = {
  max_budget: "",
  make: "",
  model: "",
  min_year: "",
  max_mileage_km: "",
  body_style: "",
  drivetrain: "",
};

const fields = [
  {
    name: "max_budget",
    label: "Maximum cash budget (CAD)",
    placeholder: "e.g. 30000",
    type: "number",
    min: 0,
  },
  {
    name: "make",
    label: "Make",
    placeholder: "e.g. Toyota",
    type: "text",
  },
  {
    name: "model",
    label: "Model",
    placeholder: "e.g. RAV4",
    type: "text",
  },
  {
    name: "min_year",
    label: "Minimum year",
    placeholder: "e.g. 2020",
    type: "number",
    min: 1900,
    max: 2100,
  },
  {
    name: "max_mileage_km",
    label: "Maximum mileage (km)",
    placeholder: "e.g. 100000",
    type: "number",
    min: 0,
  },
  {
    name: "body_style",
    label: "Body style",
    placeholder: "e.g. SUV",
    type: "text",
  },
  {
    name: "drivetrain",
    label: "Drivetrain",
    placeholder: "e.g. AWD",
    type: "text",
  },
];

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [customerText, setCustomerText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState("");
  const [extraction, setExtraction] = useState(null);
  const [editedFields, setEditedFields] = useState({});
  const [showAnomalyReview, setShowAnomalyReview] =
    useState(false);
  const publicDemo =
    import.meta.env.VITE_AUTOMATCH_PUBLIC_DEMO === "1";

  const reviewUiAvailable =
    !import.meta.env.PROD && !publicDemo;


  function handleChange(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));

    setEditedFields((previous) => ({
      ...previous,
      [name]: true,
    }));

    setMatches(null);
    setError("");
  }

  function handleClear() {
    setForm({ ...initialForm });
    setCustomerText("");
    setExtraction(null);
    setExtractionError("");
    setEditedFields({});
    setMatches(null);
    setError("");
  }


  async function handleExtract() {
    setExtractionError("");
    setExtracting(true);

    try {
      const result = await extractRequirements(customerText);

      const updatedForm = {};

      for (const field of Object.keys(initialForm)) {
        const status = result.field_states[field];
        const value = result.requirements[field];

        updatedForm[field] =
          status === "explicit" && value != null
            ? String(value)
            : "";
      }

      // Extraction replaces the previous seven filters.
      // Non-explicit values are never activated.
      setForm(updatedForm);
      setExtraction(result);
      setEditedFields({});

      // Existing search results are now outdated.
      setMatches(null);
      setError("");
    } catch (err) {
      setExtractionError(
        err instanceof Error
          ? err.message
          : "AI extraction could not be completed."
      );
    } finally {
      setExtracting(false);
    }
  }


  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setMatches(null);

    try {
      const payload = buildMatchPayload(form);

      setLoading(true);

      const nextMatches = await fetchMatches(payload);

      setMatches(nextMatches);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An unexpected error occurred."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="brand-label">
            AUTOMATCH / INVENTORY SEARCH
          </div>

          <h1>Find vehicles that fit the conversation.</h1>

          <p>
            Enter your customer's requirements and compare up
            to five available inventory candidates.
          </p>
        </div>

        <div className="header-tag">
          Salesperson workspace
        </div>
      </header>

      <main>
        {publicDemo && (
          <aside
            className="demo-notice"
            aria-label="Synthetic inventory notice"
          >
            <strong>
              Portfolio Demo — Synthetic Inventory
            </strong>

            <p>
              AutoMatch currently uses 50 fictional vehicles
              to demonstrate inventory search and partial
              matching. These vehicles are not real listings
              and are not available for purchase.
            </p>

            <p>
              AI requirement extraction is currently disabled
              in the public demo.
            </p>
          </aside>
        )}

        <InventoryStatus />


        {reviewUiAvailable && (
          <>
            <div className="anomaly-toggle-row">
              <button
                type="button"
                className="clear-button"
                aria-expanded={showAnomalyReview}
                aria-controls="anomaly-review-region"
                onClick={() =>
                  setShowAnomalyReview(
                    (previous) => !previous
                  )
                }
              >
                {showAnomalyReview
                  ? "Hide anomaly review"
                  : "Open anomaly review"}
              </button>
            </div>

            {showAnomalyReview && (
              <div id="anomaly-review-region">
                <AnomalyReview />
              </div>
            )}
          </>
        )}


        <section className="search-panel">
          <div className="section-heading">
            <div>
              <span className="section-kicker">01 / SEARCH</span>
              <h2>Customer requirements</h2>
              <p>
                Enter only the requirements the customer has
                actually specified.
              </p>
            </div>
          </div>


          <div className="ai-extraction-panel">
            <div className="form-field">
              <label htmlFor="customer_text">
                Natural-language customer requirements
              </label>

              <textarea
                id="customer_text"
                value={customerText}
                onChange={(event) => {
                  setCustomerText(event.target.value);
                  setExtraction(null);
                  setExtractionError("");
                  setMatches(null);
                }}
                placeholder={
                  "Example: I need a Toyota SUV under " +
                  "$30,000, 2020 or newer, with AWD."
                }
                rows={4}
                maxLength={1200}
                disabled={publicDemo || loading || extracting}
              />
            </div>

            <p className="ai-help-text">
              Use anonymized descriptions only. Never enter
              names, contact details, addresses, or other
              sensitive customer information. AI extraction
              replaces the seven filters below but never
              searches automatically.
            </p>

            <div className="form-actions">
              <button
                type="button"
                className="search-button"
                onClick={handleExtract}
                disabled={
                  publicDemo ||
                  loading ||
                  extracting ||
                  customerText.trim().length < 5
                }
              >
                {publicDemo
                  ? "AI extraction unavailable in public demo"
                  : extracting
                    ? "Extracting requirements..."
                    : "Extract requirements with AI"}
              </button>
            </div>

            {extracting && (
              <div className="message-panel" role="status">
                <strong>Local AI is extracting...</strong>
                <p>
                  Review the extracted fields before searching.
                </p>
              </div>
            )}

            {extractionError && (
              <div
                className="message-panel error-panel"
                role="alert"
              >
                <strong>AI extraction failed</strong>
                <p>{extractionError}</p>
                <p>
                  You can still enter requirements manually.
                </p>
              </div>
            )}

            {extraction && (
              <div className="message-panel" role="status">
                <strong>AI extraction completed</strong>

                <p>
                  Review and edit the seven fields below,
                  then click Find matching vehicles.
                </p>

                {extraction.review_notes.length > 0 && (
                  <div className="ai-review-notes">
                    <strong>Items requiring review</strong>

                    <ul>
                      {extraction.review_notes.map(
                        (note, index) => (
                          <li key={`${index}-${note}`}>
                            {note}
                          </li>
                        )
                      )}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>


          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              {fields.map((field) => (
                <div className="form-field" key={field.name}>
                  <label htmlFor={field.name}>
                    {field.label}
                  </label>

                  <input
                    id={field.name}
                    name={field.name}
                    type={field.type}
                    value={form[field.name]}
                    onChange={handleChange}
                    placeholder={field.placeholder}
                    min={field.min}
                    max={field.max}
                    step={
                      field.type === "number" ? 1 : undefined
                    }
                    disabled={loading || extracting}
                  />
                  {extraction && (
                    <p className="ai-field-feedback">
                      {editedFields[field.name] ? (
                        <span>Manually edited</span>
                      ) : (
                        <>
                          <span>
                            AI: {extraction.field_states[field.name]}
                          </span>

                          {extraction.evidence[field.name] && (
                            <span>
                              {" | Evidence: "}
                              {extraction.evidence[field.name]}
                            </span>
                          )}
                        </>
                      )}
                    </p>
                  )}
                </div>
              ))}
            </div>

            <div className="form-actions">
              <button
                className="search-button"
                type="submit"
                disabled={loading || extracting}
              >
                {loading
                  ? "Searching inventory..."
                  : "Find matching vehicles"}
              </button>

              <button
                className="clear-button"
                type="button"
                onClick={handleClear}
                disabled={loading || extracting}
              >
                Clear requirements
              </button>
            </div>
          </form>

          <div className="search-disclaimer">
            A vehicle may partially meet the requirements.
            Matching eligibility and tolerances are determined
            by the existing backend rules.
          </div>
        </section>

        <section className="results-section">
          <div className="section-heading">
            <div>
              <span className="section-kicker">02 / RESULTS</span>
              <h2>Vehicle candidates</h2>
              <p>
                Candidates are displayed in backend order,
                not ranked by preference.
              </p>
            </div>

            {matches !== null && (
              <span className="results-count">
                {matches.length} of 5 maximum
              </span>
            )}
          </div>

          {loading && (
            <div className="message-panel" role="status">
              <div className="loading-spinner" />
              <strong>Searching current inventory...</strong>
              <p>Checking the submitted requirements.</p>
            </div>
          )}

          {!loading && error && (
            <div className="message-panel error-panel" role="alert">
              <strong>Search could not be completed</strong>
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && matches === null && (
            <div className="message-panel">
              <strong>No search submitted yet</strong>
              <p>
                Fill in one or more requirements above to
                view vehicle candidates.
              </p>
            </div>
          )}

          {!loading &&
            !error &&
            matches !== null &&
            matches.length === 0 && (
              <div className="message-panel">
                <strong>No eligible vehicles found</strong>
                <p>
                  The current inventory has no candidates
                  meeting the backend's partial-match
                  eligibility rules for these requirements.
                  Adjust the requirements to try again.
                </p>
              </div>
            )}

          {!loading &&
            !error &&
            matches !== null &&
            matches.length > 0 && (
              <div className="results-grid">
                {matches.map((match) => (
                  <VehicleCard
                    key={match.id}
                    match={match}
                  />
                ))}
              </div>
            )}
        </section>
      </main>

      <footer className="app-footer">
        <span>AutoMatch</span>
        <span>
          Inventory-based partial matching · Final selection
          remains with the salesperson
        </span>
      </footer>
    </div>
  );
}