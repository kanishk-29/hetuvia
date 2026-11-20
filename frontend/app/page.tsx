"use client";

import { useEffect, useState } from "react";

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

function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mb-4 mt-1 text-sm text-slate-500">{description}</p>
      {children}
    </section>
  );
}

function Badge({ value }: { value: string | null | undefined }) {
  const text = value ?? "—";
  const tone = ["overdue", "error", "rejected", "contact_now"].includes(text)
    ? "bg-red-50 text-red-700 ring-red-200"
    : ["pending_review", "warning", "due", "deferred", "review_data_first"].includes(text)
      ? "bg-amber-50 text-amber-700 ring-amber-200"
      : ["approved", "up_to_date", "completed", "active"].includes(text)
        ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
        : "bg-slate-50 text-slate-600 ring-slate-200";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}>
      {text.replace(/_/g, " ")}
    </span>
  );
}

function formatValue(value: string | null | undefined): string {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function TableShell({ children }: { children: React.ReactNode }) {
  return <div className="overflow-x-auto rounded-lg border border-slate-200">{children}</div>;
}

const th =
  "border-b border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";
const td = "px-3 py-2 text-sm text-slate-700 align-top";

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

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">HETUVIA operator console</h1>
          <p className="mt-1 text-sm text-slate-600">
            Read-only view of stored findings, proposed pathways and audit history.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">API</span>
          <Badge value={apiStatus === "ok" ? "approved" : apiStatus === "error" ? "rejected" : "pending_review"} />
          <button
            type="button"
            onClick={() => setRefreshKey((key) => key + 1)}
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            Refresh
          </button>
        </div>
      </header>

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>DEMONSTRATION ONLY.</strong> Fictional records and placeholder rules. Not an Abu Dhabi
        guideline and not clinical advice. Human review is required before any outreach.
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Source system
          <input
            value={source}
            onChange={(event) => setSource(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Search person ID
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="e.g. SYN-0007"
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Recommendation status
          <select
            value={recommendationStatus}
            onChange={(event) => setRecommendationStatus(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          >
            <option value="">All</option>
            <option value="pending_review">Pending review</option>
            <option value="approved">Approved</option>
            <option value="deferred">Deferred</option>
            <option value="rejected">Rejected</option>
            <option value="closed">Closed</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Priority
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          >
            <option value="">All</option>
            <option value="contact_now">Contact now</option>
            <option value="review_data_first">Review data first</option>
            <option value="routine">Routine</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
          Care-gap outcome
          <select
            value={gapOutcome}
            onChange={(event) => setGapOutcome(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
          >
            <option value="">All</option>
            <option value="overdue">Overdue</option>
            <option value="due">Due</option>
            <option value="up_to_date">Up to date</option>
            <option value="not_eligible">Not eligible</option>
            <option value="not_assessable">Not assessable</option>
          </select>
        </label>
        {selectedPerson && (
          <button
            type="button"
            onClick={() => setSelectedPerson(null)}
            className="rounded-md bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-700 ring-1 ring-inset ring-sky-200"
          >
            Focused on {personLabel(selectedPerson)} — clear
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error} — make sure the API is running at the configured URL.
        </div>
      )}
      {loading && !summary && <p className="text-sm text-slate-500">Loading operator data…</p>}

      {summary && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["People", summary.people],
            ["Pending review", summary.recommendations_by_status.pending_review ?? 0],
            ["Overdue gaps", summary.care_gap_findings.overdue ?? 0],
            ["DQ findings", Object.values(summary.data_quality_findings).reduce((a, b) => a + b, 0)],
            ["Audit events", summary.audit_events],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
            </div>
          ))}
        </div>
      )}

      <Panel
        title="Work queue"
        description="Proposed pathways awaiting human review. Priority is outreach order, not clinical urgency."
      >
        <TableShell>
          <table className="min-w-full divide-y divide-slate-200">
            <thead>
              <tr>
                <th className={th}>Person</th>
                <th className={th}>Pathway</th>
                <th className={th}>Priority</th>
                <th className={th}>Status</th>
                <th className={th}>Reviewer</th>
                <th className={th}>Evaluated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {recommendations?.items.map((rec) => (
                <tr key={rec.id}>
                  <td className={td}>
                    <button
                      type="button"
                      onClick={() => setSelectedPerson(rec.person_id)}
                      className="font-medium text-sky-700 hover:underline"
                    >
                      {personLabel(rec.person_id)}
                    </button>
                  </td>
                  <td className={td}>{rec.pathway_title}</td>
                  <td className={td}><Badge value={rec.priority} /></td>
                  <td className={td}><Badge value={rec.status} /></td>
                  <td className={td}>{rec.reviewer_name ?? "—"}</td>
                  <td className={td}>{rec.evaluated_on}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
        <p className="mt-2 text-xs text-slate-500">
          Showing {recommendations?.items.length ?? 0} of {recommendations?.meta.total ?? 0}
        </p>
      </Panel>

      <Panel title="People" description="Stored records for the selected source system.">
        <TableShell>
          <table className="min-w-full divide-y divide-slate-200">
            <thead>
              <tr>
                <th className={th}>Source ID</th>
                <th className={th}>DOB</th>
                <th className={th}>Language</th>
                <th className={th}>Area</th>
                <th className={th}>Status</th>
                <th className={th}>Family history</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {people?.items.map((person) => (
                <tr key={person.person_id}>
                  <td className={`${td} font-medium`}>{person.source_record_id ?? "—"}</td>
                  <td className={td}>{person.date_of_birth ?? "unknown"}</td>
                  <td className={td}>{person.preferred_language ?? "—"}</td>
                  <td className={td}>{person.area_code ?? "—"}</td>
                  <td className={td}><Badge value={person.status} /></td>
                  <td className={td}><Badge value={person.family_history_state} /></td>
                  <td className={td}>
                    <button
                      type="button"
                      onClick={() => setSelectedPerson(person.person_id)}
                      className="text-sm text-sky-700 hover:underline"
                    >
                      Focus
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
        <p className="mt-2 text-xs text-slate-500">
          Showing {people?.items.length ?? 0} of {people?.meta.total ?? 0}
        </p>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Care-gap findings" description="Rule verdicts and the evidence that produced them.">
          <TableShell>
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr>
                  <th className={th}>Person</th>
                  <th className={th}>Rule</th>
                  <th className={th}>Outcome</th>
                  <th className={th}>Age</th>
                  <th className={th}>Due</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {gaps?.items.map((gap) => (
                  <tr key={gap.id}>
                    <td className={td}>{personLabel(gap.person_id)}</td>
                    <td className={td}>
                      {gap.rule_id} v{gap.rule_version}
                    </td>
                    <td className={td}><Badge value={gap.outcome} /></td>
                    <td className={td}>{gap.age_years ?? "—"}</td>
                    <td className={td}>{gap.due_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
          <p className="mt-2 text-xs text-slate-500">
            Showing {gaps?.items.length ?? 0} of {gaps?.meta.total ?? 0}
          </p>
        </Panel>

        <Panel title="Data-quality findings" description="Missing, uncertain or conflicting source fields.">
          <TableShell>
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr>
                  <th className={th}>Person</th>
                  <th className={th}>Rule</th>
                  <th className={th}>Field</th>
                  <th className={th}>Severity</th>
                  <th className={th}>Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {dq?.items.map((finding) => (
                  <tr key={finding.id}>
                    <td className={td}>{personLabel(finding.person_id)}</td>
                    <td className={td}>{finding.rule_code}</td>
                    <td className={td}>{finding.field_name}</td>
                    <td className={td}><Badge value={finding.severity} /></td>
                    <td className={td}>{finding.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
          <p className="mt-2 text-xs text-slate-500">
            Showing {dq?.items.length ?? 0} of {dq?.meta.total ?? 0}
          </p>
        </Panel>
      </div>

      <Panel title="Audit trail" description="Append-only history of system actions and human review decisions.">
        <TableShell>
          <table className="min-w-full divide-y divide-slate-200">
            <thead>
              <tr>
                <th className={th}>When</th>
                <th className={th}>Actor</th>
                <th className={th}>Role</th>
                <th className={th}>Action</th>
                <th className={th}>Object</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {audit?.items.map((event) => (
                <tr key={event.id}>
                  <td className={td}>{formatValue(event.occurred_at)}</td>
                  <td className={td}>{event.actor}</td>
                  <td className={td}>{event.role}</td>
                  <td className={td}>{event.action.replace(/_/g, " ")}</td>
                  <td className={td}>
                    {event.object_type} {event.object_id.slice(0, 8)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
        <p className="mt-2 text-xs text-slate-500">
          Showing {audit?.items.length ?? 0} of {audit?.meta.total ?? 0}
        </p>
      </Panel>

      <div className="flex justify-center pb-4">
        <button
          type="button"
          onClick={() => setLimit((current) => current + PAGE_SIZE)}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Show more
        </button>
      </div>
    </main>
  );
}
