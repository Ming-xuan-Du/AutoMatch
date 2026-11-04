import InventoryStatus from "./components/InventoryStatus";
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

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));

    // Prevent old results being displayed as current results.
    setMatches(null);
    setError("");
  }

  function handleClear() {
    setForm(initialForm);
    setMatches(null);
    setError("");
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
        <InventoryStatus />
        
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
                    disabled={loading}
                  />
                </div>
              ))}
            </div>

            <div className="form-actions">
              <button
                className="search-button"
                type="submit"
                disabled={loading}
              >
                {loading
                  ? "Searching inventory..."
                  : "Find matching vehicles"}
              </button>

              <button
                className="clear-button"
                type="button"
                onClick={handleClear}
                disabled={loading}
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