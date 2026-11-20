const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Page<T> = {
  items: T[];
  meta: { total: number; limit: number; offset: number };
};

export type Person = {
  person_id: string;
  source_system: string;
  source_record_id: string | null;
  date_of_birth: string | null;
  sex_recorded: string | null;
  preferred_language: string | null;
  area_code: string | null;
  status: string;
  family_history_state: string;
};

export type CareGapFinding = {
  id: string;
  person_id: string;
  source_system: string;
  rule_id: string;
  rule_version: string;
  service_type: string;
  outcome: string;
  evaluated_on: string;
  age_years: number | null;
  due_date: string | null;
  last_completed_on: string | null;
  message: string;
  evidence: Record<string, unknown>;
};

export type DataQualityFinding = {
  id: string;
  person_id: string;
  source_system: string;
  subject_table: string;
  field_name: string;
  rule_code: string;
  rule_version: string;
  severity: string;
  field_state: string | null;
  message: string;
  evaluated_on: string;
};

export type Recommendation = {
  id: string;
  person_id: string;
  source_system: string;
  kind: string;
  pathway_code: string;
  pathway_title: string;
  rule_id: string;
  status: string;
  priority: string;
  priority_reasons: string[];
  uncertainty: string;
  review_required_reason: string;
  reviewer_name: string | null;
  reviewer_note: string | null;
  reviewed_at: string | null;
  evaluated_on: string;
};

export type AuditEvent = {
  id: string;
  occurred_at: string;
  actor: string;
  role: string;
  action: string;
  object_type: string;
  object_id: string;
  person_id: string | null;
  detail: Record<string, unknown>;
};

export type Summary = {
  source_system: string | null;
  people: number;
  care_gap_findings: Record<string, number>;
  data_quality_findings: Record<string, number>;
  recommendations_by_status: Record<string, number>;
  recommendations_by_priority: Record<string, number>;
  audit_events: number;
  label: string;
};

type Params = Record<string, string | number | undefined | null>;

async function apiGet<T>(path: string, params: Params = {}): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const suffix = query.toString();
  const response = await fetch(`${API_URL}/api/v1${path}${suffix ? `?${suffix}` : ""}`);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`${path} failed (${response.status})${detail ? `: ${detail}` : ""}`);
  }
  return response.json() as Promise<T>;
}

export const fetchSummary = (source?: string) => apiGet<Summary>("/summary", { source });

export const fetchPeople = (params: {
  source?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) => apiGet<Page<Person>>("/people", params);

export const fetchCareGapFindings = (params: {
  source?: string;
  personId?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
}) => apiGet<Page<CareGapFinding>>("/care-gap-findings", {
  source: params.source,
  person_id: params.personId,
  outcome: params.outcome,
  limit: params.limit,
  offset: params.offset,
});

export const fetchDataQualityFindings = (params: {
  source?: string;
  personId?: string;
  ruleCode?: string;
  limit?: number;
  offset?: number;
}) => apiGet<Page<DataQualityFinding>>("/data-quality-findings", {
  source: params.source,
  person_id: params.personId,
  rule_code: params.ruleCode,
  limit: params.limit,
  offset: params.offset,
});

export const fetchRecommendations = (params: {
  source?: string;
  personId?: string;
  status?: string;
  priority?: string;
  limit?: number;
  offset?: number;
}) => apiGet<Page<Recommendation>>("/recommendations", {
  source: params.source,
  person_id: params.personId,
  status: params.status,
  priority: params.priority,
  limit: params.limit,
  offset: params.offset,
});

export const fetchAuditEvents = (params: {
  action?: string;
  personId?: string;
  limit?: number;
  offset?: number;
}) => apiGet<Page<AuditEvent>>("/audit-events", {
  action: params.action,
  person_id: params.personId,
  limit: params.limit,
  offset: params.offset,
});
