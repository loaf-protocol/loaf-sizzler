import unittest

from loaf_sizzler.storage.memory import MemoryStorage
from loaf_sizzler.tools.get_output import get_output


class FakeContract:
    def __init__(self):
        self.assigned = True
        self.profile = {"id": 7, "axlPublicKey": "known-caller"}

    def get_profile(self, profile_id):
        if profile_id == 7:
            return self.profile
        return {"error": "not found"}

    def is_assigned_verifier(self, job_id, profile_id):
        return self.assigned and job_id == "1" and profile_id == 7

    def get_job(self, job_id):
        return {"outputHash": ""}


class GetOutputAuthTest(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.storage.store_output("1", "worker output")
        self.contract = FakeContract()

    def test_rejects_missing_caller_identity(self):
        result = get_output({"job_id": "1", "verifier_profile_id": 7}, self.contract, self.storage, "")

        self.assertIn("error", result)
        self.assertIn("missing caller identity", result["error"])

    def test_rejects_unknown_caller_profile(self):
        result = get_output({"job_id": "1", "verifier_profile_id": 999}, self.contract, self.storage, "unknown-caller")

        self.assertIn("error", result)
        self.assertIn("verifier profile not found", result["error"])

    def test_rejects_mismatched_caller_axl_key(self):
        result = get_output({"job_id": "1", "verifier_profile_id": 7}, self.contract, self.storage, "wrong-caller")

        self.assertIn("error", result)
        self.assertIn("does not match verifier profile", result["error"])

    def test_rejects_unassigned_verifier(self):
        self.contract.assigned = False

        result = get_output({"job_id": "1", "verifier_profile_id": 7}, self.contract, self.storage, "known-caller")

        self.assertIn("error", result)
        self.assertIn("not an assigned verifier", result["error"])

    def test_returns_output_for_assigned_verifier(self):
        result = get_output({"job_id": "1", "verifier_profile_id": 7}, self.contract, self.storage, "known-caller")

        self.assertEqual(result["output"], "worker output")
        self.assertTrue(result["output_hash"].startswith("0x"))


if __name__ == "__main__":
    unittest.main()
