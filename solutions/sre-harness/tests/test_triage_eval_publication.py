"""SPEC-B1 P-B1-8: externally verified corpus/policy publication authority."""

from __future__ import annotations

from dataclasses import replace

import pytest

from sre_harness.triage.eval import (
    CorpusProvenance,
    TriageCorpusPublication,
    TriageCorpusPublicationGate,
    TriageEvalPolicy,
    TriageEvalReport,
    TriageEvidenceScope,
    VerifiedTriageCorpusPublication,
    evaluate_triage_suite,
    load_triage_seed_scenarios,
    triage_corpus_manifest_digest,
    triage_target,
)

ORIGIN = "registry://sre-governance/triage-corpora"
VERIFIER_REF = "verifier://sre-governance/triage-corpus/v1"


class _Verifier:
    verifier_ref = VERIFIER_REF

    def __init__(self, outcome: object = True) -> None:
        self.outcome = outcome

    def verify(self, publication: TriageCorpusPublication) -> bool:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome  # type: ignore[return-value]


def _policy(**updates: object) -> TriageEvalPolicy:
    values: dict[str, object] = {
        "policy_id": "b1-candidate-thresholds-v1",
        "revision": "sha256:" + "a" * 64,
        "minimum_scenarios": 3,
        "minimum_per_cause": 1,
        "minimum_pass_rate": 1.0,
        "maximum_unknown_confidence": 0.25,
    }
    values.update(updates)
    return TriageEvalPolicy(**values)  # type: ignore[arg-type]


def _curated_scenarios():
    return tuple(
        replace(
            scenario,
            ground_truth=replace(
                scenario.ground_truth,
                provenance=CorpusProvenance.CURATED_REAL,
            ),
        )
        for scenario in load_triage_seed_scenarios()
    )


def _binding(scenarios=None, policy=None, **updates: object) -> TriageCorpusPublication:
    scenarios = _curated_scenarios() if scenarios is None else tuple(scenarios)
    policy = _policy() if policy is None else policy
    values: dict[str, object] = {
        "corpus_id": "payments-b1-curated-v1",
        "corpus_revision": "sha256:" + "b" * 64,
        "policy_id": policy.policy_id,
        "policy_revision": policy.revision,
        "scenario_ids": tuple(sorted(scenario.id for scenario in scenarios)),
        "scenario_manifest_digest": triage_corpus_manifest_digest(scenarios),
        "approved_by": "sre-eval-codeowners",
        "approval_revision": "sha256:" + "c" * 64,
        "origin": ORIGIN,
        "publication_revision": "sha256:" + "d" * 64,
        "verifier_ref": VERIFIER_REF,
    }
    values.update(updates)
    return TriageCorpusPublication(**values)  # type: ignore[arg-type]


def _decision(
    binding=None,
    verifier=None,
    *,
    allowed_origins: tuple[str, ...] = (ORIGIN,),
    allowed_verifier_refs: tuple[str, ...] = (VERIFIER_REF,),
):
    return TriageCorpusPublicationGate(
        binding=_binding() if binding is None else binding,
        binding_verifier=_Verifier() if verifier is None else verifier,
        allowed_origins=allowed_origins,
        allowed_verifier_refs=allowed_verifier_refs,
    ).evaluate()


def _verified(binding: TriageCorpusPublication) -> VerifiedTriageCorpusPublication:
    decision = _decision(binding=binding)
    assert decision.admissible and decision.capability is not None
    return decision.capability


@pytest.mark.unit
class TestCorpusPublicationGate:
    def test_unconfigured_gate_fails_closed_without_calling_a_verifier(self) -> None:
        decision = TriageCorpusPublicationGate(
            binding=None,
            binding_verifier=None,
            allowed_origins=(ORIGIN,),
            allowed_verifier_refs=(VERIFIER_REF,),
        ).evaluate()

        assert decision.admissible is False
        assert decision.capability is None
        assert decision.reasons == ("corpus-publication-gate-unconfigured",)

    def test_allowlisted_exact_verification_issues_opaque_capability(self) -> None:
        decision = _decision()

        assert decision.admissible is True
        assert decision.reasons == ()
        assert type(decision.capability) is VerifiedTriageCorpusPublication
        assert decision.capability.corpus_id == "payments-b1-curated-v1"

    def test_verified_publication_cannot_be_constructed_by_caller(self) -> None:
        with pytest.raises(TypeError, match="publication gate"):
            VerifiedTriageCorpusPublication(_binding())

    def test_mutating_an_issued_capability_invalidates_the_gate_decision(self) -> None:
        decision = _decision()
        assert decision.capability is not None

        object.__setattr__(decision.capability, "corpus_id", "tampered")

        assert decision.admissible is False

    @pytest.mark.parametrize("outcome", [1, "true", RuntimeError("offline")])
    def test_verifier_requires_exact_boolean_true(self, outcome: object) -> None:
        decision = _decision(verifier=_Verifier(outcome))

        assert decision.admissible is False
        assert "corpus-publication-verification-failed" in decision.reasons

    def test_origin_and_verifier_are_allowlisted_and_exactly_joined(self) -> None:
        origin = _decision(allowed_origins=())
        verifier = _Verifier()
        verifier.verifier_ref = "verifier://attacker/corpus"
        identity = _decision(verifier=verifier)

        assert "corpus-publication-origin-not-allowed" in origin.reasons
        assert "corpus-publication-verifier-not-allowed" in identity.reasons
        assert "corpus-publication-verifier-mismatch" in identity.reasons

    def test_verifier_cannot_mutate_publication_while_attesting(self) -> None:
        class MutatingVerifier:
            verifier_ref = VERIFIER_REF

            @staticmethod
            def verify(publication: TriageCorpusPublication) -> bool:
                object.__setattr__(
                    publication,
                    "scenario_ids",
                    (*publication.scenario_ids, "injected"),
                )
                return True

        decision = _decision(verifier=MutatingVerifier())

        assert decision.admissible is False
        assert decision.reasons == ("corpus-publication-changed-during-verification",)

    @pytest.mark.parametrize(
        "updates",
        [
            {"corpus_id": " "},
            {"corpus_revision": "main"},
            {"scenario_ids": ()},
            {"scenario_ids": ("b", "a")},
            {"scenario_ids": ("a", "a")},
            {"scenario_ids": ("",)},
        ],
    )
    def test_publication_binding_is_canonical_and_closed(
        self,
        updates: dict[str, object],
    ) -> None:
        with pytest.raises(ValueError):
            _binding(**updates)


@pytest.mark.unit
class TestCorpusManifest:
    def test_manifest_is_order_independent_but_binds_labels_and_snapshot_content(
        self,
    ) -> None:
        scenarios = _curated_scenarios()
        original = triage_corpus_manifest_digest(scenarios)
        changed_truth = replace(
            scenarios[0],
            ground_truth=replace(
                scenarios[0].ground_truth,
                required_evidence_ids=("errors-payments",),
            ),
        )
        evidence = scenarios[0].snapshot.evidence
        changed_snapshot = replace(
            scenarios[0],
            snapshot=replace(
                scenarios[0].snapshot,
                evidence=(replace(evidence[0], statement="tampered"), *evidence[1:]),
            ),
        )

        assert triage_corpus_manifest_digest(reversed(scenarios)) == original
        assert triage_corpus_manifest_digest((changed_truth, *scenarios[1:])) != original
        assert triage_corpus_manifest_digest((changed_snapshot, *scenarios[1:])) != original

    def test_manifest_rejects_empty_or_duplicate_suites(self) -> None:
        scenario = _curated_scenarios()[0]

        with pytest.raises(ValueError, match="at least one"):
            triage_corpus_manifest_digest(())
        with pytest.raises(ValueError, match="unique"):
            triage_corpus_manifest_digest((scenario, scenario))


@pytest.mark.unit
class TestCorpusPublicationEvalJoin:
    def test_verified_exact_curated_publication_can_issue_eligibility(self) -> None:
        scenarios = _curated_scenarios()
        policy = _policy()
        publication = _verified(_binding(scenarios, policy))

        report = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=policy,
            publication=publication,
        )

        assert report.threshold_conformant is True
        assert report.evidence_scope is TriageEvidenceScope.CANDIDATE_CURATED
        assert report.production_evidence is publication
        assert report.production_evidence_eligible is True
        assert report.reasons == ()

    def test_even_verified_publication_cannot_promote_fixture_labels(self) -> None:
        scenarios = load_triage_seed_scenarios()
        policy = _policy()
        publication = _verified(_binding(scenarios, policy))

        report = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=policy,
            publication=publication,
        )

        assert report.evidence_scope is TriageEvidenceScope.FIXTURE_ONLY
        assert report.production_evidence_eligible is False
        assert "fixture-corpus-not-production-evidence" in report.reasons

    @pytest.mark.parametrize(
        ("updates", "reason"),
        [
            ({"policy_revision": "sha256:" + "e" * 64}, "corpus-policy-mismatch"),
            ({"scenario_ids": ("rca-deployment-regression",)}, "corpus-scenario-ids-mismatch"),
            ({"scenario_manifest_digest": "sha256:" + "f" * 64}, "corpus-manifest-mismatch"),
        ],
    )
    def test_exact_policy_ids_and_manifest_must_rejoin(
        self,
        updates: dict[str, object],
        reason: str,
    ) -> None:
        scenarios = _curated_scenarios()
        policy = _policy()
        publication = _verified(_binding(scenarios, policy, **updates))

        report = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=policy,
            publication=publication,
        )

        assert report.production_evidence_eligible is False
        assert reason in report.reasons

    def test_raw_or_post_issuance_mutated_publication_cannot_enable(self) -> None:
        scenarios = _curated_scenarios()
        policy = _policy()
        binding = _binding(scenarios, policy)
        raw = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=policy,
            publication=binding,  # type: ignore[arg-type]
        )
        verified = _verified(binding)
        object.__setattr__(verified, "publication_revision", "sha256:" + "e" * 64)
        mutated = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=policy,
            publication=verified,
        )

        assert raw.production_evidence_eligible is False
        assert mutated.production_evidence_eligible is False
        assert "verified-corpus-publication-invalid" in raw.reasons
        assert "verified-corpus-publication-invalid" in mutated.reasons

    def test_report_cannot_be_fabricated_or_mutated_after_issuance(self) -> None:
        scenarios = _curated_scenarios()
        policy = _policy()
        publication = _verified(_binding(scenarios, policy))
        report = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=policy,
            publication=publication,
        )

        with pytest.raises(TypeError, match="evaluate_triage_suite"):
            TriageEvalReport(
                summary=report.summary,
                threshold_conformant=True,
                evidence_scope=TriageEvidenceScope.CANDIDATE_CURATED,
                reasons=(),
                policy=policy,
                production_evidence=publication,
            )

        object.__setattr__(report, "reasons", ("tampered",))
        assert report.production_evidence_eligible is False
