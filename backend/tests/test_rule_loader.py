import json

import pytest

from app.services.rule_loader import DEFAULT_RULE_FILE, load_rules


def write_variant(tmp_path, **changes):
    data = json.loads(DEFAULT_RULE_FILE.read_text(encoding="utf-8"))
    data["rules"][0].update(changes)
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_shipped_rules_load_and_are_labelled_as_demonstrations():
    rules = load_rules()
    assert len(rules) == 2
    assert all(rule.status == "demonstration" for rule in rules)
    assert all("not an Abu Dhabi guideline" in rule.source for rule in rules)


def test_inverted_age_range_is_refused(tmp_path):
    with pytest.raises(ValueError):
        load_rules(write_variant(tmp_path, min_age_years=40, max_age_years=10))


def test_approved_status_is_refused_until_a_source_is_confirmed(tmp_path):
    with pytest.raises(ValueError):
        load_rules(write_variant(tmp_path, status="approved"))


def test_rule_without_a_real_source_is_refused(tmp_path):
    with pytest.raises(ValueError):
        load_rules(write_variant(tmp_path, source=""))


def test_unknown_exclusion_is_refused(tmp_path):
    with pytest.raises(ValueError):
        load_rules(write_variant(tmp_path, exclusions=["whatever"]))