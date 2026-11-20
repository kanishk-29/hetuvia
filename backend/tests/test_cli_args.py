"""Bad command-line input must be rejected by argparse with a clear message and exit code 2.

Before these checks, a mistyped date or recommendation id crashed with a traceback (a raw
ValueError) after the arguments had already been accepted. These are black-box tests of the
command lines: they call main() the way a shell would and never open a database session.
"""

import argparse
import sys
from datetime import date
from types import SimpleNamespace

import pytest

from app import cli, export_demo, workflow_cli
from app.adapters.synthetic_generator import REFERENCE_DATE

BAD_DATES = ("2026-13-01", "01/02/2026", "not-a-date", "")


@pytest.mark.parametrize("parse", [cli._date_arg, export_demo._date_arg, workflow_cli._date_arg])
@pytest.mark.parametrize("text", BAD_DATES)
def test_every_date_argument_rejects_an_unparseable_value(parse, text):
    with pytest.raises(argparse.ArgumentTypeError, match="YYYY-MM-DD"):
        parse(text)


@pytest.mark.parametrize("parse", [cli._date_arg, export_demo._date_arg, workflow_cli._date_arg])
def test_every_date_argument_accepts_a_real_date(parse):
    assert parse("2026-11-01") == date(2026, 11, 1)


def test_evaluation_date_prefers_the_date_the_operator_supplied():
    args = SimpleNamespace(date=date(2026, 5, 4), source="csv_import")
    assert cli._evaluation_date(args) == date(2026, 5, 4)


def test_evaluation_date_falls_back_to_the_reference_date_for_synthetic_data():
    assert cli._evaluation_date(SimpleNamespace(date=None, source="synthetic")) == REFERENCE_DATE


@pytest.mark.parametrize("command", ["quality-check", "care-gap-check"])
def test_check_commands_refuse_a_malformed_date_before_running(monkeypatch, command, capsys):
    monkeypatch.setattr(sys, "argv", ["app.cli", command, "--date", "01/02/2026"])
    with pytest.raises(SystemExit) as problem:
        cli.main()
    assert problem.value.code == 2
    assert "expected YYYY-MM-DD" in capsys.readouterr().err


def test_export_refuses_a_malformed_date_before_exporting(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["app.export_demo", "--date", "2026-13-45"])
    with pytest.raises(SystemExit) as problem:
        export_demo.main()
    assert problem.value.code == 2
    assert "expected YYYY-MM-DD" in capsys.readouterr().err


def test_recommend_refuses_a_malformed_date_before_running(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["app.workflow_cli", "recommend", "--date", "soon"])
    with pytest.raises(SystemExit) as problem:
        workflow_cli.main()
    assert problem.value.code == 2
    assert "expected YYYY-MM-DD" in capsys.readouterr().err


def test_review_refuses_an_id_that_is_not_a_uuid(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv",
        ["app.workflow_cli", "review", "not-a-uuid", "--decision", "approve", "--reviewer", "Dr Test"],
    )
    with pytest.raises(SystemExit) as problem:
        workflow_cli.main()
    assert problem.value.code == 2
    assert "expected a UUID" in capsys.readouterr().err
