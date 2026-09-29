"""JSON artifact adapter; business rules live exclusively in the controller."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Error as SQLiteError
from typing import Annotated

import typer
from pydantic import BaseModel

from etf_harness.controller.service import ActionRefused, CampaignController, CampaignView
from etf_harness.policy.actions import Outcome
from etf_harness.registry.sqlite import SQLiteRegistry
from etf_harness.schemas.domain import (
    Approval,
    ApprovalRequest,
    Campaign,
    Hypothesis,
    canonical_json,
)

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
campaign_app = typer.Typer(no_args_is_help=True)
hypothesis_app = typer.Typer(no_args_is_help=True)
app.add_typer(campaign_app, name="campaign")
app.add_typer(hypothesis_app, name="hypothesis")


@app.callback()
def main(
    ctx: typer.Context,
    registry: Annotated[Path, typer.Option(help="Local synthetic P1 registry")] = Path(
        ".etf-harness/registry.sqlite3"
    ),
) -> None:
    ctx.obj = registry


@contextmanager
def controller(ctx: typer.Context, *, create: bool = False) -> Iterator[CampaignController]:
    try:
        path = Path(ctx.obj)
        if not create and not path.exists():
            raise ValueError(f"Registry does not exist: {path}")
        with SQLiteRegistry(path) as registry:
            yield CampaignController(registry)
    except ActionRefused as exc:
        typer.echo(exc.decision.model_dump_json(), err=True)
        raise typer.Exit(2 if exc.decision.outcome == Outcome.REQUIRE_APPROVAL else 1) from exc
    except (ValueError, OSError, SQLiteError) as exc:
        typer.echo(canonical_json({"error": str(exc)}), err=True)
        raise typer.Exit(1) from exc


def read_artifact[T: BaseModel](path: Path, model: type[T]) -> T:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def show_status(view: CampaignView) -> None:
    typer.echo(
        canonical_json(
            {
                "campaign": view.campaign.model_dump(mode="json"),
                "revision": view.revision,
                "hypotheses": list(view.hypotheses),
                "approvals": [a.model_dump(mode="json") for a in view.approvals.values()],
                "requests": [
                    {"request": r.model_dump(mode="json"), "request_digest": r.request_digest}
                    for r in view.requests.values()
                ],
                "budget": {
                    key: {
                        "candidate_used": view.used_budget(key)[0],
                        "robustness_used": view.used_budget(key)[1],
                        "limits": hypothesis.budget.model_dump(mode="json"),
                    }
                    for key, hypothesis in view.hypotheses.items()
                },
            }
        )
    )


def show_request(request: ApprovalRequest) -> None:
    typer.echo(
        canonical_json(
            {
                "outcome": Outcome.REQUIRE_APPROVAL,
                "request": request.model_dump(mode="json"),
                "request_digest": request.request_digest,
            }
        )
    )


@campaign_app.command("create")
def create_campaign(ctx: typer.Context, file: Annotated[Path, typer.Option()]) -> None:
    with controller(ctx, create=True) as service:
        show_status(service.create(read_artifact(file, Campaign)))


@hypothesis_app.command("propose")
def propose_hypothesis(ctx: typer.Context, file: Annotated[Path, typer.Option()]) -> None:
    with controller(ctx) as service:
        show_request(service.propose(read_artifact(file, Hypothesis)))


@hypothesis_app.command("approve")
def approve_hypothesis(ctx: typer.Context, file: Annotated[Path, typer.Option()]) -> None:
    """Import a human decision (APPROVED, REJECTED, or REVISION_REQUIRED)."""
    with controller(ctx) as service:
        show_status(service.approve(read_artifact(file, Approval)))


@campaign_app.command("status")
def campaign_status(ctx: typer.Context, campaign_id: str) -> None:
    with controller(ctx) as service:
        show_status(service.status(campaign_id))


@campaign_app.command("reject")
def reject_campaign(
    ctx: typer.Context,
    campaign_id: str,
    reason: Annotated[str, typer.Option()],
    approval: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Without --approval, emit a pending administrative closure request."""
    with controller(ctx) as service:
        if approval is None:
            show_request(service.request_rejection(campaign_id, reason))
            raise typer.Exit(2)
        show_status(service.reject(campaign_id, read_artifact(approval, Approval), reason))
