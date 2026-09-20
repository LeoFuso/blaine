import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.cognition import ScriptedCognition
from runtime.kernel.context import reconstruct
from runtime.kernel.contracts import MAX_PACKET, encode, message, validate_spec, validate_decision
from runtime.kernel.execution import Capabilities, evaluate, policy_gate


def spec():
    return validate_spec(message("TaskSpec", {
        "objective": "Produce exact evidence", "capabilities": ["artifact.write", "artifact.read", "fixture.effect"],
        "autonomy": {"allowed": ["artifact.write", "artifact.read", "fixture.effect"]},
        "completion": [{"criterion": "Exact deliverable", "evidence": {
            "artifact": "answer", "sha256": hashlib.sha256(b"verified").hexdigest()}}],
    }))


def state():
    return {"task_id": "test", "revision": 0, "lifecycle": "RUNNING", "iteration": 1,
            "active_specialist": "coordinator", "spec_ref": "fixture:spec-v1", "decision_id": None,
            "decision_ref": None, "context_ref": None, "observation_ref": None, "wait": None,
            "artifacts": {}, "completion_ref": None, "result_ref": None}


def decision(action):
    return message("CognitiveDecision", {"task_id": "test", "task_revision": 0,
                   "turn_id": "test/1", "next_action": action})


class KernelContracts(unittest.TestCase):
    def test_strict_versions_fields_and_criteria(self):
        valid = message("TaskSpec", spec())
        for invalid in ({**valid, "version": True}, {**valid, "version": 2},
                        {**valid, "payload": {**spec(), "cloud": {}}},
                        {**valid, "payload": {**spec(), "completion": []}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_spec(invalid)
        with self.assertRaises(ValueError):
            encode({"value": float("nan")})

    def test_spawn_is_typed_but_denied_without_allocation(self):
        raw = decision({"type": "SPAWN_TASK", "task_spec": message("TaskSpec", spec())})
        self.assertEqual(validate_decision(raw)["next_action"]["type"], "SPAWN_TASK")
        self.assertIn("allocation", policy_gate(raw, state(), spec())["reason"])

    def test_policy_rejects_stale_invalid_and_ineligible_decisions(self):
        stale = decision({"type": "COMPLETE"})
        stale["payload"]["task_revision"] = 9
        variants = [stale, decision({"type": "DELETE_EVERYTHING"}),
                    decision({"type": "HANDOFF", "specialist": "unregistered"}),
                    decision({"type": "COMPLETE", "verified": True}),
                    {**decision({"type": "COMPLETE"}), "version": 2}]
        for raw in variants:
            with self.subTest(raw=raw):
                self.assertEqual(policy_gate(raw, state(), spec())["outcome"], "deny")

    def test_requirements_do_not_grant_authority(self):
        restricted = {**spec(), "autonomy": {"allowed": []}}
        raw = decision({"type": "INVOKE_CAPABILITY", "capability": "fixture.effect", "input": {"value": "denied"}})
        self.assertEqual(policy_gate(raw, state(), restricted)["outcome"], "deny")

    def test_wait_requires_identifiable_typed_input(self):
        for action in ({"type": "WAIT", "reason": "waiting"},
                       {"type": "WAIT", "wait_id": "input", "input_type": "anything"}):
            with self.assertRaises(ValueError):
                validate_decision(decision(action))


class KernelStorageAndContext(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = ArtifactStore(self.root / "artifacts")
        self.capabilities = Capabilities(self.store, self.root / "fixture.sqlite")

    def test_exact_artifact_replay_and_cross_task_isolation(self):
        original = "Olá\nexact bytes\x00".encode()
        ref = self.store.put("test", original)
        self.assertEqual(self.store.put("test", original), ref)
        self.assertEqual(self.store.read("test", ref), original)
        with self.assertRaises(ValueError):
            self.store.read("other", ref)
        with self.assertRaises(ValueError):
            self.store.put("../escape", b"bad")

    def test_corruption_cannot_complete(self):
        ref = self.store.put("test", b"verified")
        current = {**state(), "artifacts": {"answer": ref}}
        self.assertEqual(evaluate(spec(), current, self.store)["payload"]["outcome"], "satisfied")
        path = self.store.root / "test" / ref.rsplit(":", 1)[1]
        path.write_bytes(b"tampered")
        self.assertEqual(evaluate(spec(), current, self.store)["payload"]["outcome"], "unknown")

    def test_missing_wrong_and_exact_evidence(self):
        self.assertEqual(evaluate(spec(), state(), self.store)["payload"]["outcome"], "unsatisfied")
        ref = self.store.put("test", b"wrong")
        self.assertEqual(evaluate(spec(), {**state(), "artifacts": {"answer": ref}}, self.store)["payload"]["outcome"], "unsatisfied")

    def test_fixture_effect_is_atomic_and_idempotent(self):
        request = message("CapabilityRequest", {"task_id": "test", "operation_id": "test/1",
                          "capability": "fixture.effect", "input": {"value": "one"}})
        first = self.capabilities.execute(request)
        self.assertEqual(self.capabilities.execute(request), first)
        with sqlite3.connect(self.root / "fixture.sqlite") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM effects").fetchone()[0], 1)
        changed = {**request, "payload": {**request["payload"], "input": {"value": "two"}}}
        self.assertEqual(self.capabilities.execute(changed)["payload"]["outcome"], "failure")

    def test_context_is_selective_and_provider_cannot_override_authority(self):
        ref = self.store.put_json("test", message("PolicyDecision", {"outcome": "deny"}))
        self.store.put("test", b"IRRELEVANT_HISTORY_SENTINEL")
        current = {**state(), "observation_ref": ref, "active_specialist": "specialist"}
        item = {"source": "memory:fixture", "revision": "1", "authority": "derived",
                "content": "Unverified preference", "unknowns": ["not authoritative"]}
        packet = reconstruct(current, spec(), self.store, [lambda _: [item]])
        self.assertEqual(packet["payload"]["specialist"], "specialist")
        self.assertEqual(packet["payload"]["observations"][0]["kind"], "PolicyDecision")
        self.assertNotIn("IRRELEVANT_HISTORY_SENTINEL", encode(packet).decode())
        self.assertLess(len(encode(packet)), MAX_PACKET)
        with self.assertRaises(ValueError):
            reconstruct(current, spec(), self.store, [lambda _: [{**item, "authority": "task"}]])
        with self.assertRaises(ValueError):
            reconstruct(current, spec(), self.store, [lambda _: [{**item, "content": "x" * MAX_PACKET}]])

    def test_script_is_effect_free_and_observation_read_is_exact(self):
        raw = reconstruct(state(), spec(), self.store)
        adapter = ScriptedCognition([{"type": "COMPLETE"}])
        self.assertEqual(adapter(raw), decision({"type": "COMPLETE"}))
        self.assertEqual(list(self.store.root.iterdir()), [])

    def test_artifact_read_preserves_provenance(self):
        ref = self.store.put("test", b"verified")
        result = self.capabilities.execute(message("CapabilityRequest", {
            "task_id": "test", "operation_id": "test/2", "capability": "artifact.read", "input": {"ref": ref}}))
        self.assertEqual(result["payload"]["output"]["content"], "verified")
        self.assertEqual(result["payload"]["output"]["sha256"], hashlib.sha256(b"verified").hexdigest())


if __name__ == "__main__":
    unittest.main()
