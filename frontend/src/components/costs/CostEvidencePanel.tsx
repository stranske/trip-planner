import { useEffect, useState } from "react";

import {
  fetchCostCoverage,
  researchCostCoverage,
  updateCostCoverage,
  type CostCoverageRequirement,
  type CostCoverageResponse,
  type ResearchOption,
} from "../../api/costCoverage";

function labelFor(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatMoney(value: number | null, currency = "USD"): string | null {
  if (value == null || !Number.isFinite(value)) {
    return null;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);
}

function modeMessage(requirement: CostCoverageRequirement): string {
  if (requirement.collection_mode === "automatic") {
    return "The planner calculates this once it has the few trip-specific details below.";
  }
  if (requirement.collection_mode === "researchable") {
    return "The planner can find current options, calculate an estimate, and retain the sources.";
  }
  return "Only you or your organization can confirm this item.";
}

const AUTOMATIC_INPUTS = new Set([
  "travel_dates",
  "parking_days",
  "trip_duration_days",
  "destination",
]);
const REMEMBERED_PROFILE_INPUTS = new Set([
  "traveler_residence_address",
  "official_domicile_address",
]);

export function CostEvidencePanel({ tripId }: { tripId: string }) {
  const [coverage, setCoverage] = useState<CostCoverageResponse | null>(null);
  const [inputDrafts, setInputDrafts] = useState<Record<string, Record<string, string>>>({});
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setError(null);
    void fetchCostCoverage(tripId)
      .then((result) => {
        if (!active) return;
        setCoverage(result);
        setInputDrafts(
          Object.fromEntries(result.requirements.map((item) => [item.code, { ...item.inputs }]))
        );
        setNoteDrafts(
          Object.fromEntries(result.requirements.map((item) => [item.code, item.note ?? ""]))
        );
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : "Cost coverage could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, [tripId]);

  function adopt(result: CostCoverageResponse) {
    setCoverage(result);
    setInputDrafts((current) => ({
      ...current,
      ...Object.fromEntries(
        result.requirements.map((item) => [item.code, { ...(current[item.code] ?? {}), ...item.inputs }])
      ),
    }));
  }

  async function runResearch(requirement: CostCoverageRequirement) {
    setBusyCode(requirement.code);
    setError(null);
    try {
      adopt(await researchCostCoverage(tripId, requirement.code, inputDrafts[requirement.code] ?? {}));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The planner could not finish this research.");
    } finally {
      setBusyCode(null);
    }
  }

  async function chooseOption(requirement: CostCoverageRequirement, option: ResearchOption) {
    setBusyCode(requirement.code);
    setError(null);
    try {
      adopt(
        await updateCostCoverage(tripId, requirement.code, {
          estimate_amount: option.estimated_total ?? option.unit_rate ?? undefined,
          source_url: option.source_url,
          selected_option: option,
          note: option.notes,
          inputs: inputDrafts[requirement.code] ?? {},
        })
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The estimate could not be saved.");
    } finally {
      setBusyCode(null);
    }
  }

  async function resolveTravelerItem(
    requirement: CostCoverageRequirement,
    status: "complete" | "not_applicable"
  ) {
    setBusyCode(requirement.code);
    setError(null);
    try {
      adopt(
        await updateCostCoverage(tripId, requirement.code, {
          status,
          note: noteDrafts[requirement.code] ?? "",
          inputs: inputDrafts[requirement.code] ?? {},
        })
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The item could not be updated.");
    } finally {
      setBusyCode(null);
    }
  }

  if (error && coverage == null) {
    return (
      <section className="status-card status-card-error">
        <p className="status-label">Costs &amp; evidence</p>
        <h2>Organization requirements are temporarily unavailable</h2>
        <p role="alert">{error}</p>
      </section>
    );
  }
  if (coverage == null) {
    return <p className="muted-copy">Loading organization cost and evidence requirements…</p>;
  }

  return (
    <div className="cost-evidence-workspace">
      <section className="status-card cost-evidence-summary">
        <div>
          <p className="status-label">Costs &amp; evidence</p>
          <h2>{coverage.summary.headline}</h2>
          <p>
            The planner handles public research and calculations. It asks you only for details it
            cannot reliably determine, then carries the selected estimates and sources into the
            organization workbook.
          </p>
        </div>
        <div className="cost-evidence-count" aria-label="Coverage progress">
          <strong>{coverage.summary.resolved_count}</strong>
          <span>of {coverage.summary.requirement_count} resolved</span>
        </div>
      </section>

      {error ? <p className="planner-inline-error" role="alert">{error}</p> : null}

      <div className="cost-evidence-list">
        {coverage.requirements.map((requirement) => {
          const isBusy = busyCode === requirement.code;
          const canResearch = ["researchable", "automatic"].includes(requirement.collection_mode);
          const inputNames = Array.from(
            new Set([
              ...requirement.missing_inputs,
              ...(requirement.research
                ? requirement.required_inputs.filter((name) => !AUTOMATIC_INPUTS.has(name))
                : []),
            ])
          );
          return (
            <article className="status-card cost-evidence-card" key={requirement.code}>
              <div className="cost-evidence-heading">
                <div>
                  <p className="status-label">{labelFor(requirement.category)}</p>
                  <h3>{requirement.title}</h3>
                </div>
                <span className={`cost-evidence-status status-${requirement.status}`}>
                  {labelFor(requirement.status)}
                </span>
              </div>
              <p>{requirement.summary}</p>
              <p className="cost-evidence-assistance">{modeMessage(requirement)}</p>

              {inputNames.length > 0 ? (
                <div className="cost-evidence-inputs">
                  {inputNames.map((inputName) => (
                    <label key={inputName}>
                      <span>{labelFor(inputName)}</span>
                      <input
                        value={inputDrafts[requirement.code]?.[inputName] ?? ""}
                        onChange={(event) =>
                          setInputDrafts((current) => ({
                            ...current,
                            [requirement.code]: {
                              ...(current[requirement.code] ?? {}),
                              [inputName]: event.target.value,
                            },
                          }))
                        }
                        placeholder={`Add ${labelFor(inputName).toLowerCase()}`}
                      />
                      {REMEMBERED_PROFILE_INPUTS.has(inputName) ? (
                        <small>Saved to your travel profile for future trips.</small>
                      ) : null}
                    </label>
                  ))}
                </div>
              ) : null}

              {canResearch ? (
                <button
                  type="button"
                  className="primary-button"
                  disabled={isBusy}
                  onClick={() => void runResearch(requirement)}
                >
                  {isBusy
                    ? "Working…"
                    : requirement.research
                      ? "Refresh current options"
                      : requirement.collection_mode === "automatic"
                        ? "Calculate this for me"
                        : "Research this for me"}
                </button>
              ) : (
                <div className="cost-evidence-traveler-input">
                  <label>
                    <span>What should TPP know?</span>
                    <textarea
                      value={noteDrafts[requirement.code] ?? ""}
                      onChange={(event) =>
                        setNoteDrafts((current) => ({
                          ...current,
                          [requirement.code]: event.target.value,
                        }))
                      }
                      placeholder="Add the organization or traveler-only detail here."
                    />
                  </label>
                  <div className="button-row">
                    <button
                      type="button"
                      className="primary-button"
                      disabled={isBusy}
                      onClick={() => void resolveTravelerItem(requirement, "complete")}
                    >
                      Save as complete
                    </button>
                    {requirement.code !== "organization_attestations" ? (
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={isBusy}
                        onClick={() => void resolveTravelerItem(requirement, "not_applicable")}
                      >
                        Not applicable
                      </button>
                    ) : null}
                  </div>
                </div>
              )}

              {requirement.research ? (
                <div className="cost-evidence-results">
                  <p className="status-label">Planner research</p>
                  <p>{requirement.research.summary}</p>
                  <div className="cost-evidence-options">
                    {requirement.research.options.map((option, index) => {
                      const total = formatMoney(option.estimated_total, requirement.currency);
                      const rate = formatMoney(option.unit_rate, requirement.currency);
                      const selected = requirement.selected_option?.name === option.name;
                      return (
                        <article className="decision-card" key={`${option.name}-${index}`}>
                          <h4>{option.name}</h4>
                          {total ? <strong>{total} estimated total</strong> : null}
                          {!total && rate ? <strong>{rate}{option.unit ? ` ${option.unit}` : ""}</strong> : null}
                          <p>{option.notes}</p>
                          {option.details && Object.keys(option.details).length > 0 ? (
                            <dl className="cost-evidence-facts">
                              {Object.entries(option.details).map(([key, value]) => (
                                <div key={key}>
                                  <dt>{labelFor(key)}</dt>
                                  <dd>{String(value)}</dd>
                                </div>
                              ))}
                            </dl>
                          ) : null}
                          <div className="button-row">
                            <button
                              type="button"
                              className={selected ? "secondary-button" : "primary-button"}
                              disabled={isBusy || selected}
                              onClick={() => void chooseOption(requirement, option)}
                            >
                              {selected ? "Selected for workbook" : "Use this estimate"}
                            </button>
                            {option.source_url ? (
                              <a href={option.source_url} target="_blank" rel="noreferrer">
                                View source
                              </a>
                            ) : null}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                  {requirement.research.sources.length > 0 ? (
                    <details>
                      <summary>All sources ({requirement.research.sources.length})</summary>
                      <ul>
                        {requirement.research.sources.map((source) => (
                          <li key={source.url}>
                            <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
