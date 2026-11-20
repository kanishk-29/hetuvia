# Rule catalogue

This file was an empty placeholder. The maintained catalogues are:

- Data-quality rules: [SRS section 5.1](srs.md) and [dq_rule_catalogue.md](dq_rule_catalogue.md).
- Care-gap rules: [SRS section 5.2](srs.md) and [care_gap_rules.md](care_gap_rules.md).
- Shipped rule set: [demo_rules_v1.json](../backend/rules/demo_rules_v1.json).

All shipped rules are labelled `DEMONSTRATION`. They were invented for software testing, are not an Abu Dhabi guideline and must not be used for clinical decisions. The rule loader refuses `status: approved` until a confirmed, cited source exists.
