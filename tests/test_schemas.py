import math

import pytest
from pydantic import ValidationError

from etf_harness.schemas.domain import Budget, Campaign, ParameterBound, canonical_json, digest


def test_canonical_hash_is_order_independent_but_type_sensitive() -> None:
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})
    assert digest({"a": 1}) != digest({"a": "1"})


@pytest.mark.parametrize("candidate,robustness", [(0, 0), (-1, 0), (1, 2), (True, 0)])
def test_invalid_budgets(candidate: int, robustness: int) -> None:
    with pytest.raises(ValidationError):
        Budget(candidate=candidate, robustness=robustness)


def test_bounds_are_closed_and_do_not_accept_boolean_as_number() -> None:
    bound = ParameterBound(minimum=1, maximum=3)
    assert bound.contains(1) and bound.contains(3)
    assert not bound.contains(True) and not bound.contains(4)
    assert not ParameterBound(choices=(1,)).contains(True)
    with pytest.raises(ValidationError):
        ParameterBound(minimum=4, maximum=1)
    with pytest.raises(ValidationError):
        ParameterBound(minimum=1, maximum=3, choices=(2,))


def test_nonfinite_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ParameterBound(minimum=0, maximum=math.inf)
    with pytest.raises(ValueError):
        canonical_json({"value": math.nan})


def test_artifact_schema_and_timezone_fail_closed(campaign: Campaign) -> None:
    raw = campaign.model_dump(mode="json")
    for override in ({"unknown": 1}, {"schema_version": 2}, {"created_at": "2026-09-29T00:00:00"}):
        with pytest.raises(ValidationError):
            Campaign.model_validate({**raw, **override})
