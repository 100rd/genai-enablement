"""SPEC-B7-CIR change-induced-regression detector tests."""

from __future__ import annotations

import inspect
import math
from pathlib import Path

import pytest

from sre_harness.sentinel.detectors import (
    CHANGE_ASSOCIATION_MAX_AGE_SECONDS,
    DEFAULT_DETECTORS,
    _change_regression_finding,
    detect_change_induced_regression,
)
from sre_harness.sentinel.finding import Severity
from sre_harness.sentinel.state import ChangeRegressionWindow, SentinelState

_PREVIOUS_REVISION = "a" * 64
_DEPLOYED_REVISION = "b" * 64


def _window(**overrides: object) -> ChangeRegressionWindow:
    values: dict[str, object] = {
        "service": "payments",
        "previous_revision": _PREVIOUS_REVISION,
        "deployed_revision": _DEPLOYED_REVISION,
        "baseline_ended_at": 1000,
        "deployed_at": 1100,
        "current_started_at": 1100,
        "observed_at": 1400,
        "intervening_deployments": 0,
        "baseline_errors": 1,
        "baseline_requests": 1000,
        "current_errors": 12,
        "current_requests": 1000,
        "allowed_error_rate": 0.001,
    }
    values.update(overrides)
    return ChangeRegressionWindow(**values)  # type: ignore[arg-type]


def _detect(window: ChangeRegressionWindow):
    return detect_change_induced_regression(SentinelState(change_regression_windows=(window,)))


@pytest.mark.unit
class TestExactChangeRegressionWindow:
    def test_derives_only_rates_and_deploy_age_from_exact_aggregates(self) -> None:
        window = _window()

        assert window.baseline_rate == pytest.approx(0.001)
        assert window.current_rate == pytest.approx(0.012)
        assert window.deploy_age_seconds == 300

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("service", "", "service"),
            ("service", " payments", "service"),
            ("service", "x" * 201, "service"),
            ("previous_revision", "A" * 64, "revision"),
            ("deployed_revision", "sha256:" + "b" * 64, "revision"),
            ("deployed_revision", "b" * 63, "revision"),
            ("baseline_ended_at", True, "exact integer"),
            ("deployed_at", 1100.0, "exact integer"),
            ("current_started_at", "1100", "exact integer"),
            ("observed_at", -1, "non-negative"),
            ("observed_at", 2**63, "bounded"),
            ("intervening_deployments", True, "exact integer"),
            ("intervening_deployments", -1, "non-negative"),
            ("intervening_deployments", 1001, "at most 1000"),
            ("baseline_errors", 1.0, "exact integer"),
            ("baseline_requests", "1000", "exact integer"),
            ("current_errors", -1, "non-negative"),
            ("current_requests", 2**63, "bounded"),
            ("baseline_errors", 1001, "cannot exceed"),
            ("current_errors", 1001, "cannot exceed"),
            ("allowed_error_rate", True, "finite float"),
            ("allowed_error_rate", 1, "finite float"),
            ("allowed_error_rate", 0.0, "between zero and one"),
            ("allowed_error_rate", 1.0, "between zero and one"),
            ("allowed_error_rate", math.nan, "finite float"),
            ("allowed_error_rate", math.inf, "finite float"),
        ],
    )
    def test_invalid_or_coerced_signal_is_rejected(
        self, field: str, value: object, match: str
    ) -> None:
        values = _window().__dict__.copy()
        values[field] = value

        with pytest.raises(ValueError, match=match):
            ChangeRegressionWindow(**values)

    def test_equal_revisions_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="distinct"):
            _window(deployed_revision=_PREVIOUS_REVISION)

    @pytest.mark.parametrize(
        ("overrides", "match"),
        [
            ({"baseline_ended_at": 1101}, "baseline"),
            ({"current_started_at": 1099}, "current"),
            ({"current_started_at": 1400}, "observed"),
            ({"observed_at": 1099}, "observed"),
        ],
    )
    def test_invalid_window_order_is_rejected(
        self, overrides: dict[str, object], match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            _window(**overrides)

    def test_signal_and_state_are_frozen(self) -> None:
        window = _window()
        with pytest.raises(Exception):  # noqa: B017 — dataclass implementation detail
            window.observed_at = 1500  # type: ignore[misc]

        state = SentinelState(change_regression_windows=(window,))
        with pytest.raises(Exception):  # noqa: B017 — dataclass implementation detail
            state.change_regression_windows = ()  # type: ignore[misc]


@pytest.mark.unit
class TestChangeRegressionRule:
    def test_exact_candidate_threshold_emits_honest_high_finding(self) -> None:
        (finding,) = _detect(_window(current_errors=11))

        assert finding.detector_id == "change_induced_regression"
        assert finding.kind == "change_induced_regression"
        assert finding.severity is Severity.HIGH
        assert finding.confidence == 0.85
        assert finding.fingerprint == f"payments:{_DEPLOYED_REVISION}"
        assert finding.suggested_runbook == "triage-change-induced-regression"
        assert "associated with" in finding.rationale
        assert "caused" not in finding.rationale.lower()
        assert finding.evidence == {
            "service": "payments",
            "previous_revision": _PREVIOUS_REVISION,
            "deployed_revision": _DEPLOYED_REVISION,
            "baseline_ended_at": 1000,
            "deployed_at": 1100,
            "current_started_at": 1100,
            "observed_at": 1400,
            "deploy_age_seconds": 300,
            "intervening_deployments": 0,
            "baseline_errors": 1,
            "baseline_requests": 1000,
            "current_errors": 11,
            "current_requests": 1000,
            "baseline_rate": 0.001,
            "current_rate": 0.011,
            "candidate_threshold": 0.011,
            "allowed_error_rate": 0.001,
        }

    def test_just_below_complete_threshold_stays_silent(self) -> None:
        assert _detect(_window(current_errors=10)) == []

    def test_exact_minimum_sample_can_qualify(self) -> None:
        findings = _detect(
            _window(
                baseline_errors=0,
                baseline_requests=100,
                current_errors=1,
                current_requests=100,
            )
        )

        assert len(findings) == 1

    @pytest.mark.parametrize(
        ("baseline_requests", "current_requests"),
        [(0, 1000), (99, 1000), (1000, 0), (1000, 99), (99, 99)],
    )
    def test_insufficient_samples_stay_silent(
        self, baseline_requests: int, current_requests: int
    ) -> None:
        assert (
            _detect(
                _window(
                    baseline_errors=min(1, baseline_requests),
                    baseline_requests=baseline_requests,
                    current_errors=min(12, current_requests),
                    current_requests=current_requests,
                )
            )
            == []
        )

    def test_exact_association_age_boundary_qualifies(self) -> None:
        (finding,) = _detect(_window(observed_at=1100 + CHANGE_ASSOCIATION_MAX_AGE_SECONDS))

        assert finding.evidence["deploy_age_seconds"] == 3600

    def test_expired_association_stays_silent(self) -> None:
        assert _detect(_window(observed_at=1100 + CHANGE_ASSOCIATION_MAX_AGE_SECONDS + 1)) == []

    def test_intervening_deployment_stays_silent(self) -> None:
        assert _detect(_window(intervening_deployments=1)) == []

    def test_stable_high_baseline_is_not_a_fixed_threshold_alert(self) -> None:
        assert _detect(_window(baseline_errors=30, current_errors=35)) == []

    def test_current_rate_inside_declared_slo_budget_stays_silent(self) -> None:
        assert (
            _detect(
                _window(
                    baseline_errors=0,
                    current_errors=15,
                    allowed_error_rate=0.01,
                )
            )
            == []
        )

    def test_critical_boundary_uses_the_inherited_stricter_rule(self) -> None:
        (critical,) = _detect(_window(current_errors=51))
        (high,) = _detect(_window(current_errors=50))

        assert critical.severity is Severity.CRITICAL
        assert high.severity is Severity.HIGH

    def test_multiple_windows_preserve_input_order(self) -> None:
        state = SentinelState(
            change_regression_windows=(
                _window(service="payments"),
                _window(
                    service="search",
                    previous_revision="c" * 64,
                    deployed_revision="d" * 64,
                    current_errors=20,
                ),
            )
        )

        findings = detect_change_induced_regression(state)

        assert [finding.evidence["service"] for finding in findings] == [
            "payments",
            "search",
        ]

    def test_registry_contains_the_detector_without_action_surface(self) -> None:
        assert detect_change_induced_regression in DEFAULT_DETECTORS
        source = (
            inspect.getsource(detect_change_induced_regression)
            + inspect.getsource(_change_regression_finding)
        ).lower()
        for forbidden in (
            "requests.",
            "open(",
            "datetime.now",
            "subprocess",
            "remediat",
            "rollback",
            "merge(",
            "close(",
        ):
            assert forbidden not in source


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        root = Path(__file__).resolve().parents[3]
        spec = (root / "docs/specs/SPEC-B7-change-induced-regression-detector.md").read_text(
            encoding="utf-8"
        )
        status = (root / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (root / "solutions/sre-harness/README.md").read_text(encoding="utf-8")

        assert "spec-traceability/SPEC-B7-CIR.json" in spec
        assert "Live operation remains incomplete" in spec
        assert "correlation, never causation" in spec
        assert "solutions/sre-harness/spec-traceability/SPEC-B7-CIR.json" in status
        assert "B7 remains" in status
        assert "operationally incomplete" in status
        assert "spec-traceability/SPEC-B7-CIR.json" in readme
        assert "correlation, not causation" in readme
        assert "operationally `incomplete`" in readme
