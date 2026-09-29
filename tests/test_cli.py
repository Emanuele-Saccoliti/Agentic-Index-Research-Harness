import json
from pathlib import Path

from conftest import human_decision
from typer.testing import CliRunner

from etf_harness.cli.app import app
from etf_harness.schemas.domain import ApprovalRequest, Campaign, Hypothesis


def test_synthetic_cli_acceptance_lifecycle(
    tmp_path: Path,
    campaign: Campaign,
    hypothesis: Hypothesis,
) -> None:
    runner = CliRunner()
    registry = tmp_path / "acceptance.sqlite3"
    prefix = ["--registry", str(registry)]
    campaign_path, hypothesis_path = tmp_path / "campaign.json", tmp_path / "hypothesis.json"
    campaign_path.write_text(campaign.model_dump_json())
    hypothesis_path.write_text(hypothesis.model_dump_json())

    created = runner.invoke(app, [*prefix, "campaign", "create", "--file", str(campaign_path)])
    assert created.exit_code == 0, created.output
    assert json.loads(created.stdout)["campaign"]["state"] == "PLANNING"

    proposed = runner.invoke(
        app, [*prefix, "hypothesis", "propose", "--file", str(hypothesis_path)]
    )
    assert proposed.exit_code == 0, proposed.output
    envelope = json.loads(proposed.stdout)
    assert envelope["outcome"] == "REQUIRE_APPROVAL"
    request = ApprovalRequest.model_validate(envelope["request"])
    assert envelope["request_digest"] == request.request_digest

    parked = runner.invoke(app, [*prefix, "campaign", "status", campaign.id])
    assert json.loads(parked.stdout)["campaign"]["state"] == "AWAITING_APPROVAL"
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(human_decision(request).model_dump_json())
    approved = runner.invoke(app, [*prefix, "hypothesis", "approve", "--file", str(approval_path)])
    assert approved.exit_code == 0, approved.output
    assert json.loads(approved.stdout)["campaign"]["state"] == "APPROVED"

    rejection_request = runner.invoke(
        app,
        [
            *prefix,
            "campaign",
            "reject",
            campaign.id,
            "--reason",
            "Synthetic acceptance complete",
        ],
    )
    assert rejection_request.exit_code == 2, rejection_request.output
    closure = ApprovalRequest.model_validate(json.loads(rejection_request.stdout)["request"])
    close_path = tmp_path / "closure.json"
    close_path.write_text(human_decision(closure, "APR-CLOSE").model_dump_json())
    rejected = runner.invoke(
        app,
        [
            *prefix,
            "campaign",
            "reject",
            campaign.id,
            "--reason",
            "Synthetic acceptance complete",
            "--approval",
            str(close_path),
        ],
    )
    assert rejected.exit_code == 0, rejected.output
    assert json.loads(rejected.stdout)["campaign"]["state"] == "REJECTED"
    reopened = runner.invoke(app, [*prefix, "campaign", "status", campaign.id])
    assert reopened.exit_code == 0
    assert json.loads(reopened.stdout) == json.loads(rejected.stdout)


def test_cli_rejects_malformed_artifact_without_partial_campaign(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"id": "incomplete"}')
    result = CliRunner().invoke(
        app,
        [
            "--registry",
            str(tmp_path / "bad.sqlite3"),
            "campaign",
            "create",
            "--file",
            str(path),
        ],
    )
    assert result.exit_code == 1
    assert "error" in json.loads(result.stderr)


def test_status_does_not_create_missing_registry(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    result = CliRunner().invoke(app, ["--registry", str(path), "campaign", "status", "missing"])
    assert result.exit_code == 1
    assert not path.exists()
