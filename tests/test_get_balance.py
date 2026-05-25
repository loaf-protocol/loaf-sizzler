import unittest
from unittest.mock import patch

from loaf_sizzler.contract_client import ContractClient
from loaf_sizzler.tools.get_balance import get_balance


class FakeConfig:
    wallet_address = "0xabc"
    workflow_ids = {}


class GetBalanceTest(unittest.TestCase):
    @patch("loaf_sizzler.contract_client.LoafConfig", return_value=FakeConfig())
    def test_get_balance_uses_wallet_address_from_local_config(self, _config):
        contract = ContractClient(axl_client=None, storage=None)

        result = get_balance({}, contract)

        self.assertEqual(result["wallet_address"], "0xabc")
        self.assertEqual(result["source"], ".loaf_config.json")
        self.assertEqual(result["usdc"], 0)
        self.assertIn("not implemented", result["note"])

    @patch("loaf_sizzler.contract_client.LoafConfig", return_value=type("Config", (), {"wallet_address": None})())
    def test_get_balance_reports_missing_wallet_address(self, _config):
        contract = ContractClient(axl_client=None, storage=None)

        result = get_balance({}, contract)

        self.assertIn("error", result)
        self.assertIn("wallet_address missing", result["error"])


if __name__ == "__main__":
    unittest.main()
