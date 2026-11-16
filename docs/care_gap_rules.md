# Care-gap rules (Chunk 6)

Rules live in backend/rules/demo_rules_v1.json and are copied into guideline_rules by the loader.
Every rule is labelled DEMONSTRATION: placeholders invented for software testing, not an Abu Dhabi
guideline. An 'approved' status is refused by the loader until a confirmed, cited source exists.

Outcomes: overdue, due, up_to_date, not_eligible, not_assessable.
- not_assessable is an information gap, not a care gap. It is used when the date of birth is missing,
  or when a completed service has no date and might be more recent than the dated ones.
- Only overdue, due and not_assessable are stored in care_gap_findings. Other counts are in the run summary.
- Declined, missed and pending screenings do not count as completed. Whether to contact someone who
  declined is an outreach decision (Chunk 10), not a care-gap decision.
- A person who never completed a service is due from the day they became eligible (or the rule's
  effective date, if later).
- Same input and same rule version always give the same verdict.
