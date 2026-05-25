import unittest

from loaf_sizzler.contract_client import ContractClient
from loaf_sizzler.storage.memory import MemoryStorage
from loaf_sizzler.tools.get_inbox import get_inbox
from loaf_sizzler.tools.list_jobs import list_jobs
from loaf_sizzler.tools.list_review_jobs import list_review_jobs


class FakeContract(ContractClient):
    def __init__(self):
        self.state_queries = []
        self.jobs_by_state = {
            0: [1],
            1: [2],
            2: [3],
        }

    def _get_job_ids_by_state(self, state: int):
        self.state_queries.append(state)
        return self.jobs_by_state.get(state, [])

    def get_job(self, job_id: int) -> dict:
        return {"jobId": job_id, "posterProfileId": 10 + job_id}

    def get_profile(self, profile_id: int) -> dict:
        return {"axlPublicKey": f"axl-{profile_id}"}


class ScanFallbackContract(FakeContract):
    def __init__(self):
        super().__init__()
        self.jobs_by_state = {}

    def get_job(self, job_id: int) -> dict:
        if job_id == 1:
            return self._normalize_job_payload({
                "result": [
                    "1",
                    "10",
                    [],
                    "criteria",
                    "0x00",
                    "1000",
                    "1000",
                    "1",
                    "1",
                    "0",
                    "0",
                    "0",
                    "1777988320",
                    "0",
                ],
                "success": True,
            }, job_id)
        return {"error": "not found"}


class JobStateListingTest(unittest.TestCase):
    def test_list_jobs_defaults_to_open(self):
        contract = FakeContract()

        result = list_jobs({}, contract)

        self.assertEqual(contract.state_queries, [0])
        self.assertEqual(result["jobs"][0]["jobId"], 1)
        self.assertEqual(result["jobs"][0]["poster_axl_key"], "axl-11")

    def test_list_jobs_accepts_semantic_state(self):
        contract = FakeContract()

        result = list_jobs({"state": "in_review"}, contract)

        self.assertEqual(contract.state_queries, [2])
        self.assertEqual(result["jobs"][0]["jobId"], 3)

    def test_list_review_jobs_uses_in_review_state(self):
        contract = FakeContract()

        result = list_review_jobs({}, contract)

        self.assertEqual(contract.state_queries, [2])
        self.assertEqual(result["jobs"][0]["jobId"], 3)

    def test_list_jobs_rejects_unknown_state(self):
        contract = FakeContract()

        result = list_jobs({"state": "waiting"}, contract)

        self.assertIn("error", result)
        self.assertIn("unknown job state", result["error"])

    def test_list_jobs_falls_back_to_scanning_direct_jobs(self):
        contract = ScanFallbackContract()

        result = list_jobs({"state": "open"}, contract)

        self.assertEqual(result["jobs"][0]["jobId"], 1)
        self.assertEqual(result["jobs"][0]["state"], 0)
        self.assertEqual(result["jobs"][0]["stateName"], "open")
        self.assertEqual(result["jobs"][0]["poster_axl_key"], "axl-1")

    def test_get_inbox_can_filter_by_type(self):
        storage = MemoryStorage()
        storage.add_message({"type": "bid", "job_id": "1"})
        storage.add_message({"type": "settlement", "job_id": "2"})

        result = get_inbox({"type": "bid"}, storage)

        self.assertEqual(result["messages"], [{"type": "bid", "job_id": "1"}])


if __name__ == "__main__":
    unittest.main()
