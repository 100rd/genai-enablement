"""SPEC-B7-DRIFT config↔state drift detector tests."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from sre_harness.sentinel.detectors import (
    DEFAULT_DETECTORS,
    DRIFT_GRACE_SECONDS,
    DRIFT_HIGH_AGE_SECONDS,
    DRIFT_MIN_CONSECUTIVE_OBSERVATIONS,
    _drift_finding,
    detect_config_state_drift,
)
from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.scan import run_sentinel
from sre_harness.sentinel.serialization import state_from_dict
from sre_harness.sentinel.state import DriftObservation, SentinelState

_TRACKING_POLICY_REVISION = "c" * 64
_DESIRED_REVISION = "b" * 64
_OBSERVED_REVISION = "a" * 64


def _observation(**overrides: object) -> DriftObservation:
    values: dict[str, object] = {
        "resource_kind": "deployment",
        "resource_id": "prod-eu-1/payments",
        "tracking_policy_revision": _TRACKING_POLICY_REVISION,
        "desired_revision": _DESIRED_REVISION,
        "observed_revision": _OBSERVED_REVISION,
        "desired_recorded_at": 1000,
        "mismatch_started_at": 1100,
        "observed_at": 1400,
        "consecutive_mismatches": 2,
    }
    values.update(overrides)
    return DriftObservation(**values)  # type: ignore[arg-type]


def _row(**overrides: object) -> dict[str, object]:
    values = _observation().__dict__.copy()
    values.update(overrides)
    return values


def _detect(observation: DriftObservation) -> list[Finding]:
    return detect_config_state_drift(SentinelState(drift_observations=(observation,)))


@pytest.mark.unit
class TestExactDriftObservation:
    def test_derives_only_mismatch_age_from_exact_normalized_fact(self) -> None:
        observation = _observation()

        assert observation.drift_age_seconds == 300

    def test_matching_and_missing_observations_are_representable_without_raw_content(self) -> None:
        matching = _observation(
            observed_revision=_DESIRED_REVISION,
            mismatch_started_at=None,
            consecutive_mismatches=0,
        )
        missing = _observation(observed_revision=None)

        assert matching.drift_age_seconds == 0
        assert missing.observed_revision is None
        assert missing.drift_age_seconds == 300

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("resource_kind", "", "resource_kind"),
            ("resource_kind", " deployment", "resource_kind"),
            ("resource_kind", "x" * 101, "resource_kind"),
            ("resource_kind", "deploy\nment", "resource_kind"),
            ("resource_id", "", "resource_id"),
            ("resource_id", "prod eu/payments", "resource_id"),
            ("resource_id", "https://example.invalid/private", "resource_id"),
            ("resource_id", "x" * 201, "resource_id"),
            ("tracking_policy_revision", "C" * 64, "revision"),
            ("desired_revision", "sha256:" + "b" * 64, "revision"),
            ("observed_revision", "a" * 63, "revision"),
            ("desired_recorded_at", True, "exact integer"),
            ("desired_recorded_at", 1000.0, "exact integer"),
            ("observed_at", "1400", "exact integer"),
            ("observed_at", -1, "non-negative"),
            ("observed_at", 2**63, "bounded"),
            ("mismatch_started_at", True, "exact integer"),
            ("mismatch_started_at", 1100.0, "exact integer"),
            ("mismatch_started_at", -1, "non-negative"),
            ("mismatch_started_at", 2**63, "bounded"),
            ("consecutive_mismatches", True, "exact integer"),
            ("consecutive_mismatches", -1, "non-negative"),
            ("consecutive_mismatches", 1_000_001, "at most"),
        ],
    )
    def test_invalid_or_coerced_signal_is_rejected(
        self, field: str, value: object, match: str
    ) -> None:
        values = _observation().__dict__.copy()
        values[field] = value

        with pytest.raises(ValueError, match=match):
            DriftObservation(**values)

    def test_desired_observation_order_is_exact(self) -> None:
        with pytest.raises(ValueError, match="desired"):
            _observation(desired_recorded_at=1401)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"observed_revision": _DESIRED_REVISION, "consecutive_mismatches": 1},
            {
                "observed_revision": _DESIRED_REVISION,
                "mismatch_started_at": 1100,
                "consecutive_mismatches": 0,
            },
        ],
    )
    def test_matching_revision_rejects_mismatch_evidence(
        self, overrides: dict[str, object]
    ) -> None:
        with pytest.raises(ValueError, match="matching"):
            _observation(**overrides)

    @pytest.mark.parametrize(
        ("overrides", "match"),
        [
            ({"mismatch_started_at": None}, "mismatch start"),
            ({"consecutive_mismatches": 0}, "at least one"),
            ({"mismatch_started_at": 999}, "desired"),
            ({"mismatch_started_at": 1401}, "observed"),
        ],
    )
    def test_mismatch_requires_consistent_persistence_evidence(
        self, overrides: dict[str, object], match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            _observation(**overrides)

    def test_signal_and_state_are_frozen(self) -> None:
        observation = _observation()
        with pytest.raises(Exception):  # noqa: B017 — dataclass implementation detail
            observation.observed_at = 1500  # type: ignore[misc]

        state = SentinelState(drift_observations=(observation,))
        with pytest.raises(Exception):  # noqa: B017 — dataclass implementation detail
            state.drift_observations = ()  # type: ignore[misc]


@pytest.mark.unit
class TestDriftRule:
    def test_exact_persistence_boundary_emits_bounded_medium_finding(self) -> None:
        (finding,) = _detect(
            _observation(
                mismatch_started_at=1400 - DRIFT_GRACE_SECONDS,
                consecutive_mismatches=DRIFT_MIN_CONSECUTIVE_OBSERVATIONS,
            )
        )

        assert finding.detector_id == "config_state_drift"
        assert finding.kind == "config_state_drift"
        assert finding.severity is Severity.MEDIUM
        assert finding.confidence == 0.95
        assert finding.fingerprint == "deployment:prod-eu-1/payments"
        assert finding.suggested_runbook == "triage-config-state-drift"
        assert "differs from" in finding.rationale
        assert finding.evidence == {
            "resource_kind": "deployment",
            "resource_id": "prod-eu-1/payments",
            "tracking_policy_revision": _TRACKING_POLICY_REVISION,
            "desired_revision": _DESIRED_REVISION,
            "observed_revision": _OBSERVED_REVISION,
            "desired_recorded_at": 1000,
            "mismatch_started_at": 1100,
            "observed_at": 1400,
            "drift_age_seconds": 300,
            "consecutive_mismatches": 2,
            "observed_present": True,
        }
        assert not {
            "manifest",
            "config",
            "diff",
            "secret",
            "credentials",
            "provider_error",
        } & set(finding.evidence)

    def test_one_observation_stays_silent(self) -> None:
        assert _detect(_observation(consecutive_mismatches=1)) == []

    def test_299_second_mismatch_stays_silent(self) -> None:
        assert _detect(_observation(mismatch_started_at=1101)) == []

    def test_matching_revision_stays_silent(self) -> None:
        assert (
            _detect(
                _observation(
                    observed_revision=_DESIRED_REVISION,
                    mismatch_started_at=None,
                    consecutive_mismatches=0,
                )
            )
            == []
        )

    def test_one_hour_persistent_digest_mismatch_is_high(self) -> None:
        (high,) = _detect(
            _observation(
                desired_recorded_at=0,
                mismatch_started_at=0,
                observed_at=DRIFT_HIGH_AGE_SECONDS,
            )
        )
        (medium,) = _detect(
            _observation(
                desired_recorded_at=0,
                mismatch_started_at=0,
                observed_at=DRIFT_HIGH_AGE_SECONDS - 1,
            )
        )

        assert high.severity is Severity.HIGH
        assert medium.severity is Severity.MEDIUM

    def test_persistent_missing_observation_is_high_and_honest(self) -> None:
        (finding,) = _detect(_observation(observed_revision=None))

        assert finding.severity is Severity.HIGH
        assert finding.evidence["observed_present"] is False
        assert finding.evidence["observed_revision"] is None
        assert "is absent from observed state" in finding.rationale

    def test_multiple_observations_preserve_input_order(self) -> None:
        state = SentinelState(
            drift_observations=(
                _observation(resource_id="prod-eu-1/payments"),
                _observation(resource_id="prod-eu-1/search", observed_revision="d" * 64),
            )
        )

        findings = detect_config_state_drift(state)

        assert [finding.evidence["resource_id"] for finding in findings] == [
            "prod-eu-1/payments",
            "prod-eu-1/search",
        ]

    def test_registry_contains_pure_action_free_detector(self) -> None:
        assert DEFAULT_DETECTORS[-1] is detect_config_state_drift
        source = (
            inspect.getsource(detect_config_state_drift) + inspect.getsource(_drift_finding)
        ).lower()
        for forbidden in (
            "requests.",
            "open(",
            "datetime.now",
            "subprocess",
            "patch(",
            "apply(",
            "sync(",
            "remediat",
            "rollback",
            "merge(",
            "close(",
        ):
            assert forbidden not in source


@pytest.mark.unit
class TestDriftSerialization:
    def test_parses_exact_mismatch_and_nullable_matching_rows(self) -> None:
        state = state_from_dict(
            {
                "drift_observations": [
                    _row(),
                    _row(
                        resource_id="prod-eu-1/search",
                        observed_revision=_DESIRED_REVISION,
                        mismatch_started_at=None,
                        consecutive_mismatches=0,
                    ),
                ]
            }
        )

        assert state.drift_observations == (
            _observation(),
            _observation(
                resource_id="prod-eu-1/search",
                observed_revision=_DESIRED_REVISION,
                mismatch_started_at=None,
                consecutive_mismatches=0,
            ),
        )

    def test_array_must_be_a_list(self) -> None:
        with pytest.raises(ValueError, match="drift_observations"):
            state_from_dict({"drift_observations": {"not": "a list"}})

    def test_unknown_top_level_field_rejects_the_complete_snapshot(self) -> None:
        with pytest.raises(ValueError, match="unexpected field"):
            state_from_dict(
                {
                    "drift_observations": [_row()],
                    "raw_manifest": {"secret": "must-not-be-ignored"},
                }
            )

    def test_array_limit_is_checked_before_row_parsing(self) -> None:
        with pytest.raises(ValueError, match="at most 1000"):
            state_from_dict({"drift_observations": [None] * 1001})

    @pytest.mark.parametrize(
        "field",
        [
            "resource_kind",
            "resource_id",
            "tracking_policy_revision",
            "desired_revision",
            "observed_revision",
            "desired_recorded_at",
            "mismatch_started_at",
            "observed_at",
            "consecutive_mismatches",
        ],
    )
    def test_missing_key_is_rejected_including_nullable_fields(self, field: str) -> None:
        row = _row()
        del row[field]

        with pytest.raises(ValueError, match="drift observation"):
            state_from_dict({"drift_observations": [row]})

    def test_extra_field_is_rejected(self) -> None:
        row = _row(raw_manifest={"secret": "no"})

        with pytest.raises(ValueError, match="unexpected field"):
            state_from_dict({"drift_observations": [row]})

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("resource_kind", 7, "resource_kind"),
            ("resource_id", ["payments"], "resource_id"),
            ("tracking_policy_revision", 7, "tracking_policy_revision"),
            ("desired_revision", None, "desired_revision"),
            ("observed_revision", 7, "observed_revision"),
            ("desired_recorded_at", True, "desired_recorded_at"),
            ("mismatch_started_at", 1100.0, "mismatch_started_at"),
            ("observed_at", "1400", "observed_at"),
            ("consecutive_mismatches", 2.0, "consecutive_mismatches"),
        ],
    )
    def test_rejects_coercion_and_wrong_nullability(
        self, field: str, value: object, match: str
    ) -> None:
        row = _row()
        row[field] = value

        with pytest.raises(ValueError, match=match):
            state_from_dict({"drift_observations": [row]})

    def test_non_mapping_row_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="drift observation"):
            state_from_dict({"drift_observations": ["not-an-object"]})


@pytest.mark.unit
class TestDriftDedup:
    def test_open_condition_stays_suppressed_when_observed_digest_changes(self) -> None:
        (first,) = run_sentinel(SentinelState(drift_observations=(_observation(),))).findings
        changed = SentinelState(drift_observations=(_observation(observed_revision="d" * 64),))

        second = run_sentinel(changed, open_findings=(first,))

        assert second.findings == ()
        assert [finding.dedup_key for finding in second.suppressed] == [first.dedup_key]

    def test_different_resource_remains_fresh(self) -> None:
        (first,) = run_sentinel(SentinelState(drift_observations=(_observation(),))).findings
        other = SentinelState(drift_observations=(_observation(resource_id="prod-eu-1/search"),))

        report = run_sentinel(other, open_findings=(first,))

        assert len(report.findings) == 1
        assert report.suppressed == ()

    def test_higher_ranked_same_key_duplicate_wins_within_scan(self) -> None:
        medium = _detect(_observation())[0]
        high = _detect(_observation(observed_revision=None))[0]

        def duplicate_detector(_: SentinelState) -> list[Finding]:
            return [medium, high]

        report = run_sentinel(SentinelState(), detectors=(duplicate_detector,))

        assert report.findings == (high,)


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        root = Path(__file__).resolve().parents[3]
        spec = (root / "docs/specs/SPEC-B7-drift-detector.md").read_text(encoding="utf-8")
        status = (root / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (root / "solutions/sre-harness/README.md").read_text(encoding="utf-8")

        assert "spec-traceability/SPEC-B7-DRIFT.json" in spec
        assert "Live operation remains incomplete" in spec
        assert "no reconciliation" in spec
        assert "solutions/sre-harness/spec-traceability/SPEC-B7-DRIFT.json" in status
        assert "B7 remains" in status
        assert "operationally incomplete" in status
        assert "spec-traceability/SPEC-B7-DRIFT.json" in readme
        assert "no reconciliation authority" in readme
        assert "operationally `incomplete`" in readme
