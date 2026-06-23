"""Unit tests for best-effort change-request parsers (k8s manifest / PR diff).

These extend the structured-payload parser with best-effort extraction of
``service``, ``target_cluster_ids`` and ``required_storageclasses`` from a k8s
manifest dict or a unified PR diff. Written first (RED).
"""

from __future__ import annotations

import pytest

from sre_harness.change_parsers import parse_k8s_manifest, parse_pr_diff


@pytest.mark.unit
class TestK8sManifestParser:
    def test_statefulset_volume_claim_templates(self) -> None:
        manifest = {
            "kind": "StatefulSet",
            "metadata": {"name": "orders", "labels": {"cluster": "prod-eu-1"}},
            "spec": {
                "volumeClaimTemplates": [
                    {"spec": {"storageClassName": "gold"}},
                    {"spec": {"storageClassName": "silver"}},
                ]
            },
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=[])
        assert req.service == "orders"
        assert req.target_cluster_ids == ["prod-eu-1"]
        assert req.required_storageclasses == {"gold", "silver"}

    def test_pvc_top_level_storageclassname(self) -> None:
        manifest = {
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "cache"},
            "spec": {"storageClassName": "fast"},
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=["prod-us-1"])
        assert req.service == "cache"
        assert req.target_cluster_ids == ["prod-us-1"]
        assert req.required_storageclasses == {"fast"}

    def test_missing_clusters_raises(self) -> None:
        manifest = {
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "cache"},
            "spec": {"storageClassName": "fast"},
        }
        with pytest.raises(ValueError, match="cluster"):
            parse_k8s_manifest(manifest, fallback_clusters=[])

    def test_missing_name_raises(self) -> None:
        manifest = {"kind": "PersistentVolumeClaim", "spec": {"storageClassName": "fast"}}
        with pytest.raises(ValueError, match="name"):
            parse_k8s_manifest(manifest, fallback_clusters=["prod-eu-1"])


@pytest.mark.unit
class TestPrDiffParser:
    def test_extracts_added_storageclassnames(self) -> None:
        diff = (
            "diff --git a/k8s/orders.yaml b/k8s/orders.yaml\n"
            "--- a/k8s/orders.yaml\n"
            "+++ b/k8s/orders.yaml\n"
            "@@\n"
            "       resources:\n"
            "+      storageClassName: gold\n"
            "-      storageClassName: bronze\n"
            "+      storageClassName: silver\n"
        )
        req = parse_pr_diff(diff, service="orders", fallback_clusters=["prod-eu-1", "prod-us-1"])
        assert req.service == "orders"
        # only *added* lines count; removed bronze is ignored
        assert req.required_storageclasses == {"gold", "silver"}
        assert req.target_cluster_ids == ["prod-eu-1", "prod-us-1"]

    def test_no_storageclass_changes_yields_empty_set(self) -> None:
        diff = "+++ b/README.md\n+some docs\n"
        req = parse_pr_diff(diff, service="orders", fallback_clusters=["prod-eu-1"])
        assert req.required_storageclasses == set()

    def test_missing_clusters_raises(self) -> None:
        with pytest.raises(ValueError, match="cluster"):
            parse_pr_diff("+storageClassName: gold\n", service="x", fallback_clusters=[])

    def test_missing_service_raises(self) -> None:
        with pytest.raises(ValueError, match="service"):
            parse_pr_diff("+storageClassName: gold\n", service="", fallback_clusters=["c"])

    def test_non_dict_volume_claim_template_ignored(self) -> None:
        manifest = {
            "kind": "StatefulSet",
            "metadata": {"name": "orders", "labels": {"cluster": "prod-eu-1"}},
            "spec": {
                "volumeClaimTemplates": [
                    "not-a-dict",
                    {"spec": {"storageClassName": "gold"}},
                ]
            },
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=[])
        assert req.required_storageclasses == {"gold"}


@pytest.mark.unit
class TestK8sNamespaceExtraction:
    def test_metadata_namespace_becomes_required_namespace(self) -> None:
        manifest = {
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "cache", "namespace": "payments"},
            "spec": {"storageClassName": "fast"},
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=["prod-eu-1"])
        assert req.required_namespaces == frozenset({"payments"})

    def test_absent_namespace_yields_empty_set(self) -> None:
        manifest = {
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "cache"},
            "spec": {"storageClassName": "fast"},
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=["prod-eu-1"])
        assert req.required_namespaces == frozenset()


@pytest.mark.unit
class TestK8sBlastRadiusActions:
    def test_high_blast_radius_kind_maps_to_action(self) -> None:
        manifest = {
            "kind": "DBInstance",  # AWS ACK / Crossplane RDS
            "metadata": {"name": "orders-db", "labels": {"cluster": "prod-eu-1"}},
            "spec": {},
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=[])
        assert "rds_param_change" in req.actions

    def test_iam_kind_maps_to_iam_change(self) -> None:
        manifest = {
            "kind": "Role",
            "metadata": {"name": "orders-role", "labels": {"cluster": "prod-eu-1"}},
            "spec": {},
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=[])
        assert "iam_change" in req.actions

    def test_ordinary_kind_has_no_actions(self) -> None:
        manifest = {
            "kind": "StatefulSet",
            "metadata": {"name": "orders", "labels": {"cluster": "prod-eu-1"}},
            "spec": {"volumeClaimTemplates": [{"spec": {"storageClassName": "gold"}}]},
        }
        req = parse_k8s_manifest(manifest, fallback_clusters=[])
        assert req.actions == frozenset()


@pytest.mark.unit
class TestPrDiffBlastRadiusActions:
    def test_added_rds_resource_maps_to_action(self) -> None:
        diff = (
            "+++ b/infra/db.tf\n"
            '+resource "aws_db_instance" "orders" {\n'
            '+  identifier = "orders"\n'
        )
        req = parse_pr_diff(diff, service="orders", fallback_clusters=["prod-eu-1"])
        assert "rds_param_change" in req.actions

    def test_added_iam_and_sg_resources_map_to_actions(self) -> None:
        diff = (
            "+++ b/infra/iam.tf\n"
            '+resource "aws_iam_policy" "orders" {\n'
            '+resource "aws_security_group" "orders" {\n'
        )
        req = parse_pr_diff(diff, service="orders", fallback_clusters=["prod-eu-1"])
        assert {"iam_change", "security_group_change"} <= req.actions

    def test_removed_high_risk_line_ignored(self) -> None:
        diff = '-resource "aws_db_instance" "old" {\n+some docs\n'
        req = parse_pr_diff(diff, service="orders", fallback_clusters=["prod-eu-1"])
        assert req.actions == frozenset()
