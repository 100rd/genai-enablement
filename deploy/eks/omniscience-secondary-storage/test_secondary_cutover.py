"""Exercise the secondary-store full-render gate without a cluster."""

import copy
import json
import unittest
from unittest.mock import patch

import secondary_cutover as cutover


def statefulset(name, volume, containers, init=None):
    pod = {
        "volumes": [{"name": "configuration", "configMap": {"name": name}}],
        "containers": [{"name": item, "image": "baseline", "volumeMounts": [
            {"name": volume, "mountPath": "/data"},
        ]} for item in containers],
    }
    if init is not None:
        pod["initContainers"] = [{"name": init, "image": "baseline"}]
    return {"spec": {"replicas": 1, "serviceName": name, "template": {"spec": pod},
                     "volumeClaimTemplates": [{"metadata": {"name": volume}}]}}


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.nats = "nats-incident-111111111111"
        self.qdrant = "omniscience-qdrant-stage-222222222222"
        self.baseline = {
            ("Deployment", "omniscience-api"): {"spec": {"replicas": 1}},
            ("StatefulSet", cutover.NATS): statefulset(cutover.NATS, "omniscience-nats-js", ["nats", "reloader"]),
            ("StatefulSet", cutover.QDRANT): statefulset(
                cutover.QDRANT, "qdrant-storage", ["qdrant"], "ensure-dir-ownership",
            ),
            ("ConfigMap", cutover.QDRANT): {"data": {
                "initialize.sh": cutover.QDRANT_FIRST_PEER,
                "production.yaml": "cluster:\n  p2p:\n    port: 6335\nservice:\n  enable_tls: false\n",
            }},
            ("Secret", "database"): {"data": {"key": "fixture"}},
            ("Service", cutover.QDRANT): {"spec": {"selector": {"app": cutover.QDRANT}}},
        }
        qdrant_pod = self.baseline[("StatefulSet", cutover.QDRANT)]["spec"]["template"]["spec"]
        qdrant_pod["volumes"].extend([
            {"name": "qdrant-config", "configMap": {"name": cutover.QDRANT, "defaultMode": 755}},
            {"name": "qdrant-secret", "secret": {"secretName": "qdrant-key", "defaultMode": 600}},
        ])
        self.helm = copy.deepcopy(self.baseline)
        cutover.set_api_paused(self.helm)
        cutover.expected_nats(self.helm, self.nats)

    def test_rejects_unrelated_changes_before_postrender(self):
        for key in (("Secret", "database"), ("Service", cutover.QDRANT), ("StatefulSet", cutover.QDRANT)):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.helm)
                candidate[key]["foreign"] = True
                with self.assertRaisesRegex(RuntimeError, "Unexpected rendered resource changes"):
                    cutover.verify_helm_render(self.baseline, candidate, self.nats)

    def test_renders_exact_claims_and_preserves_rest_service_and_mounts(self):
        key = ("ConfigMap", cutover.QDRANT)
        with patch.object(cutover, "QDRANT_CONFIG_SHA", cutover.capture.canonical_hash(self.baseline[key]["data"])):
            result = copy.deepcopy(self.helm)
            cutover.qdrant_postrender(result, self.qdrant)
            cutover.verify_final_render(self.baseline, result, self.nats, self.qdrant)
            drifted = copy.deepcopy(result)
            drifted[("Secret", "database")]["data"]["key"] = "changed"
            with self.assertRaisesRegex(RuntimeError, "Secret/database"):
                cutover.verify_final_render(self.baseline, drifted, self.nats, self.qdrant)
        self.assertEqual(result[("Deployment", "omniscience-api")]["spec"]["replicas"], 0)
        for name, claim in ((cutover.NATS, self.nats), (cutover.QDRANT, self.qdrant)):
            sts = result[("StatefulSet", name)]["spec"]
            self.assertNotIn("volumeClaimTemplates", sts)
            self.assertEqual(sts["template"]["spec"]["volumes"][-1]["persistentVolumeClaim"], {"claimName": claim})
            self.assertEqual(sts["template"]["spec"]["nodeSelector"], cutover.ON_DEMAND)
            self.assertEqual(sts["serviceName"], name)
        qdrant_volumes = {
            item["name"]: item for item in result[("StatefulSet", cutover.QDRANT)]["spec"]["template"]["spec"]["volumes"]
        }
        self.assertEqual(qdrant_volumes["qdrant-config"]["configMap"]["defaultMode"], 0o755)
        self.assertEqual(qdrant_volumes["qdrant-secret"]["secret"]["defaultMode"], 0o600)
        self.assertIn("host: 127.0.0.1", result[key]["data"]["production.yaml"])
        self.assertIn("service:\n  enable_tls: false", result[key]["data"]["production.yaml"])
        self.assertIn(cutover.qdrant_stage.PEER_URI, result[key]["data"]["initialize.sh"])
        self.assertEqual(result[("Service", cutover.QDRANT)], self.baseline[("Service", cutover.QDRANT)])
        self.assertEqual(result[("Secret", "database")], self.baseline[("Secret", "database")])

    def test_refuses_unreviewed_qdrant_config(self):
        with self.assertRaisesRegex(RuntimeError, "config digest"):
            cutover.qdrant_postrender(copy.deepcopy(self.helm), self.qdrant)

    def test_rendered_hooks_must_match_pinned_hook_manifests(self):
        hook = {"kind": "Job", "metadata": {"name": "bootstrap"}, "spec": {"suspend": True}}
        resource = {"kind": "Service", "metadata": {"name": "unchanged"}}
        rendered = "NAME: omniscience\nHOOKS:\n" + json.dumps(hook) + "\nMANIFEST:\n" + json.dumps(resource)
        self.assertEqual(cutover.read_helm_render(rendered, {("Job", "bootstrap"): hook}),
                         {("Service", "unchanged"): resource})
        with self.assertRaisesRegex(RuntimeError, "Job/bootstrap"):
            cutover.read_helm_render(rendered, {("Job", "bootstrap"): {**hook, "spec": {"suspend": False}}})

    def test_postrenderer_leaves_non_qdrant_document_text_intact(self):
        resources = []
        for (kind, name), spec in self.helm.items():
            resources.append({"kind": kind, "metadata": {"name": name}, **spec})
        unchanged = '# exact original document\n' + json.dumps(resources[-1]) + "\n"
        stream = "".join("---\n" + json.dumps(item) + "\n" for item in resources[:-1]) + "---\n" + unchanged
        config = self.helm[("ConfigMap", cutover.QDRANT)]["data"]
        with patch.object(cutover, "QDRANT_CONFIG_SHA", cutover.capture.canonical_hash(config)):
            result = cutover.postrender(stream, self.qdrant)
        self.assertTrue(result.endswith(unchanged))
        self.assertIn(self.qdrant, result)


if __name__ == "__main__":
    unittest.main()
