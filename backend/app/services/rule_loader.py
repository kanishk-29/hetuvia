"""Load and validate the labelled rule file, and copy it into the guideline_rules table."""

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import RuleStatus
from app.db.models import GuidelineRule
from app.services.care_gap_types import RuleDefinition

DEFAULT_RULE_FILE = Path(__file__).resolve().parents[2] / "rules" / "demo_rules_v1.json"


class _RuleModel(BaseModel):
    rule_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    service_type: str = Field(min_length=1)
    status: Literal["demonstration"]  # an 'approved' rule needs a confirmed, cited source first
    min_age_years: int = Field(ge=0)
    max_age_years: int = Field(ge=0)
    interval_days: int = Field(gt=0)
    lead_days: int = Field(ge=0)
    grace_days: int = Field(ge=0)
    exclusions: list[Literal["inactive_person"]] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    source: str = Field(min_length=10)

    @model_validator(mode="after")
    def _consistent(self):
        if self.max_age_years < self.min_age_years:
            raise ValueError("max_age_years must not be below min_age_years")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class _RuleFile(BaseModel):
    rule_set: str
    label: str
    rules: list[_RuleModel] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_duplicates(self):
        keys = [(r.rule_id, r.version) for r in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate (rule_id, version) in rule file")
        return self


def load_rules(path: Path | str = DEFAULT_RULE_FILE) -> list[RuleDefinition]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    parsed = _RuleFile.model_validate(data)
    return [RuleDefinition(**{**r.model_dump(), "exclusions": tuple(r.exclusions)}) for r in parsed.rules]


def _rule_values(rule: RuleDefinition) -> dict:
    """The mutable columns that define a rule version's meaning."""
    return {
        "title": rule.title,
        "service_type": rule.service_type,
        "status": RuleStatus(rule.status),
        "min_age_years": rule.min_age_years,
        "max_age_years": rule.max_age_years,
        "interval_days": rule.interval_days,
        "lead_days": rule.lead_days,
        "grace_days": rule.grace_days,
        "exclusions": list(rule.exclusions),
        "effective_from": rule.effective_from,
        "effective_to": rule.effective_to,
        "source": rule.source,
    }


def sync_rules(db: Session, rules: list[RuleDefinition]) -> int:
    """Insert new rule versions; never edit an existing version in place. Flushes; caller commits."""
    for rule in rules:
        values = _rule_values(rule)
        row = db.scalars(select(GuidelineRule).where(
            GuidelineRule.rule_id == rule.rule_id, GuidelineRule.version == rule.version)).first()
        if row is None:
            row = GuidelineRule(rule_id=rule.rule_id, version=rule.version)
            db.add(row)
        else:
            current = {name: getattr(row, name) for name in values}
            if current != values:
                raise ValueError(
                    f"rule {rule.rule_id} v{rule.version} already exists with different content; "
                    "bump the version instead of editing it in place"
                )
        for name, value in values.items():
            setattr(row, name, value)
    db.flush()
    return len(rules)