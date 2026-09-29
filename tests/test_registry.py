import sqlite3
from pathlib import Path

import pytest

from etf_harness.controller.service import CampaignController
from etf_harness.registry.base import RegistryError, RevisionConflict
from etf_harness.registry.sqlite import SQLiteRegistry
from etf_harness.schemas.domain import Campaign


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE events SET event_json = '{}'",
        "DELETE FROM events",
        "INSERT OR REPLACE INTO events SELECT record_id, campaign_id, revision, '{}' FROM events",
        "REPLACE INTO events SELECT record_id, campaign_id, revision, '{}' FROM events",
    ],
)
def test_sql_cannot_edit_delete_or_replace_history(
    tmp_path: Path,
    service: CampaignController,
    campaign: Campaign,
    sql: str,
) -> None:
    service.create(campaign)
    before = service.registry.events(campaign.id)
    with sqlite3.connect(tmp_path / "registry.sqlite3") as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(sql)
    assert service.registry.events(campaign.id) == before


def test_failed_batch_rolls_back_every_record(registry: SQLiteRegistry, campaign: Campaign) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        registry.append(campaign.id, 0, [campaign, campaign])
    assert registry.events(campaign.id) == ()


def test_stale_revision_does_not_append(registry: SQLiteRegistry, campaign: Campaign) -> None:
    registry.append(campaign.id, 0, [campaign])
    with pytest.raises(RevisionConflict):
        registry.append(campaign.id, 0, [campaign.model_copy(update={"id": "other"})])
    assert len(registry.events(campaign.id)) == 1


def test_unknown_database_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RegistryError, match="version"):
        SQLiteRegistry(path)


def test_malformed_appended_event_fails_closed(
    registry: SQLiteRegistry,
    tmp_path: Path,
    campaign: Campaign,
) -> None:
    registry.append(campaign.id, 0, [campaign])
    with sqlite3.connect(tmp_path / "registry.sqlite3") as connection:
        connection.execute("INSERT INTO events VALUES (?, ?, ?, ?)", ("bad", campaign.id, 2, "{}"))
    with pytest.raises(RegistryError, match="schema"):
        registry.events(campaign.id)
