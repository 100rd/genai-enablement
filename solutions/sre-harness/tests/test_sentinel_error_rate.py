"""SPEC-B7 error-rate-vs-baseline detector and exact signal tests."""

from __future__ import annotations

import inspect
import math
from pathlib import Path

import pytest

from sre_harness.sentinel.detectors import (
    DEFAULT_DETECTORS,
    ERROR_RATE_ABSOLUTE_DELTA,
    ERROR_RATE_BASELINE_MULTIPLIER,
    ERROR_RATE_BUDGET_MULTIPLIER,
    ERROR_RATE_CRITICAL_ABSOLUTE_DELTA,
    ERROR_RATE_CRITICAL_BASELINE_MULTIPLIER,
    ERROR_RATE_CRITICAL_BUDGET_MULTIPLIER,
    ERROR_RATE_MIN_REQUESTS,
    detect_error_rate_vs_baseline,
)
from sre_harness.sentinel.finding import Severity
from sre_harness.sentinel.state import ErrorRateWindow, SentinelState


def _window(**overrides: object) -> ErrorRateWindow:
    values: dict[str, object] = {
        "service": "payments",
        "baseline_errors": 1,
        "baseline_requests": 1000,
        "current_errors": 12,
        "current_requests": 1000,
        "allowed_error_rate": 0.001,
    }
    values.update(overrides)
    return ErrorRateWindow(**values)  # type: ignore[arg-type]


def _detect(window: ErrorRateWindow):
    return detect_error_rate_vs_baseline(SentinelState(error_rate_windows=(window,)))


@pytest.mark.unit
class TestExactErrorRateWindow:
    def test_rates_are_derived_from_exact_aggregate_counts(self) -> None:
        window = _window()

        assert window.baseline_rate == pytest.approx(0.001)
        assert window.current_rate == pytest.approx(0.012)

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("service", "", "service"),
            ("service", " payments", "service"),
            ("service", "x" * 201, "service"),
            ("baseline_errors", True, "exact integer"),
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
        values = {
            "service": "payments",
            "baseline_errors": 1,
            "baseline_requests": 1000,
            "current_errors": 12,
            "current_requests": 1000,
            "allowed_error_rate": 0.001,
        }
        values[field] = value

        with pytest.raises(ValueError, match=match):
            ErrorRateWindow(**values)  # type: ignore[arg-type]

    def test_signal_and_state_are_frozen(self) -> None:
        window = _window()
        with pytest.raises(Exception):  # noqa: B017 — dataclass implementation detail
            window.current_errors = 99  # type: ignore[misc]

        state = SentinelState(error_rate_windows=(window,))
        with pytest.raises(Exception):  # noqa: B017 — dataclass implementation detail
            state.error_rate_windows = ()  # type: ignore[misc]


@pytest.mark.unit
class TestErrorRateRule:
    def test_exact_candidate_threshold_fires_high(self) -> None:
        # baseline=0.1%; max(0.3%, 1.1%, 0.2%) == 1.1%.
        (finding,) = _detect(_window(current_errors=11))

        assert finding.detector_id == "error_rate_vs_baseline"
        assert finding.kind == "error_rate_regression"
        assert finding.severity is Severity.HIGH
        assert finding.confidence == 0.9
        assert finding.fingerprint == "payments"
        assert finding.suggested_runbook == "triage-error-rate-regression"
        assert finding.evidence == {
            "service": "payments",
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
        baseline_errors = min(1, baseline_requests)
        current_errors = min(12, current_requests)

        assert (
            _detect(
                _window(
                    baseline_errors=baseline_errors,
                    baseline_requests=baseline_requests,
                    current_errors=current_errors,
                    current_requests=current_requests,
                )
            )
            == []
        )

    def test_stable_high_baseline_is_not_a_fixed_threshold_alert(self) -> None:
        assert _detect(_window(baseline_errors=30, current_errors=35)) == []

    def test_current_rate_inside_declared_slo_budget_multiplier_stays_silent(self) -> None:
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

    def test_critical_boundary_uses_stricter_relative_and_budget_rule(self) -> None:
        (critical,) = _detect(_window(current_errors=51))
        (high,) = _detect(_window(current_errors=50))

        assert critical.severity is Severity.CRITICAL
        assert high.severity is Severity.HIGH

    def test_multiple_windows_preserve_input_order_and_silence_clean_service(self) -> None:
        state = SentinelState(
            error_rate_windows=(
                _window(service="payments"),
                _window(service="search", baseline_errors=30, current_errors=35),
                _window(service="orders", current_errors=20),
            )
        )

        findings = detect_error_rate_vs_baseline(state)

        assert [finding.fingerprint for finding in findings] == ["payments", "orders"]

    def test_rule_constants_match_the_spec_candidate(self) -> None:
        assert ERROR_RATE_MIN_REQUESTS == 100
        assert ERROR_RATE_BASELINE_MULTIPLIER == 3.0
        assert ERROR_RATE_ABSOLUTE_DELTA == 0.01
        assert ERROR_RATE_BUDGET_MULTIPLIER == 2.0
        assert ERROR_RATE_CRITICAL_BASELINE_MULTIPLIER == 5.0
        assert ERROR_RATE_CRITICAL_ABSOLUTE_DELTA == 0.05
        assert ERROR_RATE_CRITICAL_BUDGET_MULTIPLIER == 10.0

    def test_default_registry_contains_the_detector_without_action_surface(self) -> None:
        assert detect_error_rate_vs_baseline in DEFAULT_DETECTORS
        source = inspect.getsource(detect_error_rate_vs_baseline).lower()
        for forbidden in ("requests.", "open(", "subprocess", "remediat", "merge(", "close("):
            assert forbidden not in source


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        harness_root = Path(__file__).parents[1]
        repository = harness_root.parents[1]
        spec = (repository / "docs/specs/SPEC-B7-error-rate-baseline-detector.md").read_text(
            encoding="utf-8"
        )
        status = (repository / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (harness_root / "README.md").read_text(encoding="utf-8")
        normalized_spec = " ".join(spec.split())
        normalized_status = " ".join(status.split())
        normalized_readme = " ".join(readme.split())

        assert "SPEC-B7.json" in normalized_spec
        assert "B7 live operation remains incomplete" in normalized_spec
        assert "stores no PASS result" in normalized_spec
        assert "SPEC-B7.json" in normalized_status
        assert "B7 remains operationally incomplete" in normalized_status
        assert "spec-traceability/SPEC-B7.json" in normalized_readme
        assert "production calibration" in normalized_readme
