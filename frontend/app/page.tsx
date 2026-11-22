"use client";

import { useEffect, useLayoutEffect, useState } from "react";

import { fetchHealth } from "@/lib/api/health";
import {
  fetchAuditEvents,
  fetchCareGapFindings,
  fetchDataQualityFindings,
  fetchPeople,
  fetchRecommendations,
  fetchSummary,
  type AuditEvent,
  type CareGapFinding,
  type DataQualityFinding,
  type Page,
  type Person,
  type Recommendation,
  type Summary,
} from "@/lib/api/operator";

const PAGE_SIZE = 20;
const THEME_KEY = "hetuvia-theme";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

function toggleTheme() {
  const current: Theme = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  const next: Theme = current === "dark" ? "light" : "dark";
  applyTheme(next);
  try {
    window.localStorage.setItem(THEME_KEY, next);
  } catch {
    // Storage may be unavailable in private browsing; the in-memory theme still works.
  }
}

function Panel({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="panel-desc">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function Badge({ value }: { value: string | null | undefined }) {
  const text = value ?? "—";
  const tone = ["overdue", "error", "rejected", "contact_now"].includes(text)
    ? "danger"
    : ["pending_review", "warning", "due", "deferred", "review_data_first"].includes(text)
      ? "warning"
      : ["approved", "up_to_date", "completed", "active"].includes(text)
        ? "success"
        : "neutral";
  return <span className={`badge badge-${tone}`}>{text.replace(/_/g, " ")}</span>;
}

function formatValue(value: string | null | undefined): string {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function TableShell({ children }: { children: React.ReactNode }) {
  return <div className="table-wrap">{children}</div>;
}

export default function Home() {
  const [apiStatus, setApiStatus] = useState<"loading" | "ok" | "error">("loading");
  const [source, setSource] = useState("synthetic");
  const [search, setSearch] = useState("");
  const [recommendationStatus, setRecommendationStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [gapOutcome, setGapOutcome] = useState("");
  const [selectedPerson, setSelectedPerson] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [refreshKey, setRefreshKey] = useState(0);

  const [summary, setSummary] = useState<Summary | null>(null);
  const [people, setPeople] = useState<Page<Person> | null>(null);
  const [gaps, setGaps] = useState<Page<CareGapFinding> | null>(null);
  const [dq, setDq] = useState<Page<DataQualityFinding> | null>(null);
  const [recommendations, setRecommendations] = useState<Page<Recommendation> | null>(null);
  const [audit, setAudit] = useState<Page<AuditEvent> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // The inline script in the root layout applies the saved theme before paint.
  // Re-applying here keeps development's Strict Mode remount from clearing it.
  useLayoutEffect(() => {
    try {
      const stored = window.localStorage.getItem(THEME_KEY);
      if (stored === "light" || stored === "dark") applyTheme(stored);
    } catch {
      // Keep the server-rendered light theme when storage is unavailable.
    }
  }, []);

  useEffect(() => {
    fetchHealth()
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("error"));
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchSummary(source || undefined),
      fetchPeople({ source: source || undefined, search, limit }),
      fetchCareGapFindings({
        source: source || undefined,
        personId: selectedPerson ?? undefined,
        outcome: gapOutcome || undefined,
        limit,
      }),
      fetchDataQualityFindings({
        source: source || undefined,
        personId: selectedPerson ?? undefined,
        limit,
      }),
      fetchRecommendations({
        source: source || undefined,
        personId: selectedPerson ?? undefined,
        status: recommendationStatus || undefined,
        priority: priority || undefined,
        limit,
      }),
      fetchAuditEvents({ personId: selectedPerson ?? undefined, limit }),
    ])
      .then(([s, p, g, d, r, a]) => {
        if (cancelled) return;
        setError(null);
        setSummary(s);
        setPeople(p);
        setGaps(g);
        setDq(d);
        setRecommendations(r);
        setAudit(a);
      })
      .catch((problem: unknown) => {
        if (!cancelled) setError(problem instanceof Error ? problem.message : "Unable to load operator data");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [source, search, gapOutcome, recommendationStatus, priority, selectedPerson, limit, refreshKey]);

  const personLabel = (id: string) =>
    people?.items.find((person) => person.person_id === id)?.source_record_id ?? id.slice(0, 8);

  const metrics = summary
    ? [
        { label: "People", value: summary.people, hint: "Stored records for this source" },
        {
          label: "Pending review",
          value: summary.recommendations_by_status.pending_review ?? 0,
          hint: "Proposals awaiting a human decision",
        },
        {
          label: "Overdue gaps",
          value: summary.care_gap_findings.overdue ?? 0,
          hint: "Rule outcomes only, not a risk score",
        },
        {
          label: "DQ findings",
          value: Object.values(summary.data_quality_findings).reduce((a, b) => a + b, 0),
          hint: "Completeness and consistency flags",
        },
        { label: "Audit events", value: summary.audit_events, hint: "Recorded actions and decisions" },
      ]
    : [];

  return (
    <main className="app-shell">
      <header className="masthead">
        <div className="brand-line">
          <span className="brand-mark" aria-hidden="true">H</span>
          <div>
            <p className="eyebrow">Preventive care coordination · prototype</p>
            <h1>HETUVIA operator console</h1>
          </div>
        </div>
        <div className="top-actions">
          <span className={`status-pill status-${apiStatus}`}>
            <span className="status-dot" aria-hidden="true" />
            API {apiStatus === "ok" ? "connected" : apiStatus === "error" ? "offline" : "checking"}
          </span>
          <button type="button" className="btn btn-quiet theme-toggle" onClick={toggleTheme} aria-label="Toggle colour theme">
            <span className="theme-sun" aria-hidden="true">☀</span>
            <span className="theme-moon" aria-hidden="true">☾</span>
            <span className="theme-label-light">Dark mode</span>
            <span className="theme-label-dark">Light mode</span>
          </button>
          <button type="button" className="btn btn-primary" onClick={() => setRefreshKey((key) => key + 1)}>
            Refresh
          </button>
        </div>
      </header>

      <div className="safety-banner">
        <strong>DEMONSTRATION ONLY.</strong> Every record is fictional and every rule is a placeholder. This is not an
        Abu Dhabi guideline and not clinical advice. Human review is required before any outreach; this console cannot
        change a record.
      </div>

      <section className="orientation" aria-label="How to read this console">
        <article className="orientation-card">
          <span className="orientation-index">01</span>
          <div>
            <h2>What you are seeing</h2>
            <p>Stored findings from the synthetic source, not live patient data. Counts describe the demonstration population only.</p>
          </div>
        </article>
        <article className="orientation-card">
          <span className="orientation-index">02</span>
          <div>
            <h2>What a proposal means</h2>
            <p>Pathways are draft suggestions for a reviewer. Priority orders the work queue; it is not clinical urgency.</p>
          </div>
        </article>
        <article className="orientation-card">
          <span className="orientation-index">03</span>
          <div>
            <h2>What can change</h2>
            <p>Nothing here. Review and clinical actions stay in the CLI until authentication and authorisation exist.</p>
          </div>
        </article>
      </section>

      <section className="filter-panel" aria-labelledby="filters-heading">
        <div className="filter-head">
          <h2 id="filters-heading">Narrow the view</h2>
          <p>Filters apply to the findings and people tables below. Clear the focus to return to the whole population.</p>
        </div>
        <div className="filter-grid">
          <label className="field">
            <span>Source system</span>
            <input className="control" value={source} onChange={(event) => setSource(event.target.value)} />
          </label>
          <label className="field">
            <span>Search person ID</span>
            <input
              className="control"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="e.g. SYN-0007"
            />
          </label>
          <label className="field">
            <span>Recommendation status</span>
            <select
              className="control"
              value={recommendationStatus}
              onChange={(event) => setRecommendationStatus(event.target.value)}
            >
              <option value="">All</option>
              <option value="pending_review">Pending review</option>
              <option value="approved">Approved</option>
              <option value="deferred">Deferred</option>
              <option value="rejected">Rejected</option>
              <option value="closed">Closed</option>
            </select>
          </label>
          <label className="field">
            <span>Priority</span>
            <select className="control" value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="">All</option>
              <option value="contact_now">Contact now</option>
              <option value="review_data_first">Review data first</option>
              <option value="routine">Routine</option>
            </select>
          </label>
          <label className="field">
            <span>Care-gap outcome</span>
            <select className="control" value={gapOutcome} onChange={(event) => setGapOutcome(event.target.value)}>
              <option value="">All</option>
              <option value="overdue">Overdue</option>
              <option value="due">Due</option>
              <option value="up_to_date">Up to date</option>
              <option value="not_eligible">Not eligible</option>
              <option value="not_assessable">Not assessable</option>
            </select>
          </label>
        </div>
        {selectedPerson && (
          <div className="focus-bar">
            <span>
              Focused on <strong>{personLabel(selectedPerson)}</strong>. Findings, proposals and audit history are filtered to this person.
            </span>
            <button type="button" className="btn btn-quiet btn-small" onClick={() => setSelectedPerson(null)}>
              Clear focus
            </button>
          </div>
        )}
      </section>

      {error && <div className="alert alert-error" role="alert">{error} — make sure the API is running at the configured URL.</div>}
      {loading && !summary && <p className="loading-note">Loading operator data…</p>}

      {summary && (
        <section className="metrics" aria-label="Summary counts">
          {metrics.map((metric) => (
            <article className="metric-card" key={metric.label}>
              <p className="metric-label">{metric.label}</p>
              <p className="metric-value">{metric.value}</p>
              <p className="metric-hint">{metric.hint}</p>
            </article>
          ))}
        </section>
      )}

      <Panel
        title="Work queue"
        description="Proposed pathways waiting for a reviewer. Each row is a draft; a human decision is required before outreach."
      >
        <TableShell>
          <table className="data-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Pathway</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Reviewer</th>
                <th>Evaluated</th>
              </tr>
            </thead>
            <tbody>
              {recommendations?.items.map((rec) => (
                <tr key={rec.id}>
                  <td>
                    <button type="button" className="link-button" onClick={() => setSelectedPerson(rec.person_id)}>
                      {personLabel(rec.person_id)}
                    </button>
                  </td>
                  <td>{rec.pathway_title}</td>
                  <td><Badge value={rec.priority} /></td>
                  <td><Badge value={rec.status} /></td>
                  <td>{rec.reviewer_name ?? "—"}</td>
                  <td>{rec.evaluated_on}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
        <p className="row-count">Showing {recommendations?.items.length ?? 0} of {recommendations?.meta.total ?? 0} proposals</p>
      </Panel>

      <Panel title="People" description="Stored records for the selected source. Select a person to focus every panel on their data.">
        <TableShell>
          <table className="data-table">
            <thead>
              <tr>
                <th>Source ID</th>
                <th>DOB</th>
                <th>Language</th>
                <th>Area</th>
                <th>Status</th>
                <th>Family history</th>
                <th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {people?.items.map((person) => (
                <tr key={person.person_id}>
                  <td className="strong-cell">{person.source_record_id ?? "—"}</td>
                  <td>{person.date_of_birth ?? "unknown"}</td>
                  <td>{person.preferred_language ?? "—"}</td>
                  <td>{person.area_code ?? "—"}</td>
                  <td><Badge value={person.status} /></td>
                  <td>{person.family_history_state.replace(/_/g, " ")}</td>
                  <td>
                    <button type="button" className="btn btn-quiet btn-small" onClick={() => setSelectedPerson(person.person_id)}>
                      Focus
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
        <p className="row-count">Showing {people?.items.length ?? 0} of {people?.meta.total ?? 0} people</p>
      </Panel>

      <div className="panel-pair">
        <Panel title="Care-gap findings" description="Rule outcomes that may need attention. An outcome is not a diagnosis.">
          <TableShell>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Rule</th>
                  <th>Outcome</th>
                  <th>Age</th>
                  <th>Due</th>
                </tr>
              </thead>
              <tbody>
                {gaps?.items.map((gap) => (
                  <tr key={gap.id}>
                    <td>
                      <button type="button" className="link-button" onClick={() => setSelectedPerson(gap.person_id)}>
                        {personLabel(gap.person_id)}
                      </button>
                    </td>
                    <td>{gap.rule_id} v{gap.rule_version}</td>
                    <td><Badge value={gap.outcome} /></td>
                    <td>{gap.age_years ?? "—"}</td>
                    <td>{gap.due_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
          <p className="row-count">Showing {gaps?.items.length ?? 0} of {gaps?.meta.total ?? 0} findings</p>
        </Panel>

        <Panel title="Data-quality findings" description="Missing or conflicting fields that can block a safe proposal.">
          <TableShell>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Rule</th>
                  <th>Field</th>
                  <th>Severity</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {dq?.items.map((finding) => (
                  <tr key={finding.id}>
                    <td>
                      <button type="button" className="link-button" onClick={() => setSelectedPerson(finding.person_id)}>
                        {personLabel(finding.person_id)}
                      </button>
                    </td>
                    <td>{finding.rule_code}</td>
                    <td>{finding.field_name.replace(/_/g, " ")}</td>
                    <td><Badge value={finding.severity} /></td>
                    <td>{finding.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
          <p className="row-count">Showing {dq?.items.length ?? 0} of {dq?.meta.total ?? 0} findings</p>
        </Panel>
      </div>

      <Panel title="Audit trail" description="Append-only history of system actions and human review decisions.">
        <TableShell>
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Role</th>
                <th>Action</th>
                <th>Object</th>
              </tr>
            </thead>
            <tbody>
              {audit?.items.map((event) => (
                <tr key={event.id}>
                  <td>{formatValue(event.occurred_at)}</td>
                  <td>{event.actor}</td>
                  <td>{event.role}</td>
                  <td>{event.action.replace(/_/g, " ")}</td>
                  <td>{event.object_type} {event.object_id.slice(0, 8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
        <p className="row-count">Showing {audit?.items.length ?? 0} of {audit?.meta.total ?? 0} events</p>
      </Panel>

      <div className="more-row">
        <button type="button" className="btn btn-quiet" onClick={() => setLimit((current) => current + PAGE_SIZE)}>
          Show more rows
        </button>
      </div>
    </main>
  );
}
