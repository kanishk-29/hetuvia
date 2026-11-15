# CSV import format (Chunk 4)

Folder with any of: people.csv, encounters.csv, observations.csv. Header row required, UTF-8.
Load order is fixed: people, then encounters, then observations. Records are matched only by
(source system, source_record_id). Nothing is merged by name, date of birth or address.

| File | Columns (all must be present in the header) |
|---|---|
| people.csv | source_record_id, date_of_birth, sex_recorded, preferred_language, area_code, family_history_state |
| encounters.csv | source_record_id, person_source_id, encounter_type, encounter_date, status |
| observations.csv | source_record_id, person_source_id, encounter_source_id, observation_type, value, unit, value_state, observed_at |

Rules: dates are YYYY-MM-DD and never in the future. A blank date_of_birth means unknown.
family_history_state and value_state must be explicit; a blank is never read as "no".
value is required when value_state is present and must be blank otherwise.
Accepted units are checked, never converted: height cm, weight kg, systolic_blood_pressure mmHg.
Bad rows go to import_rejections with a reason. Rows already imported are skipped and left unchanged.
