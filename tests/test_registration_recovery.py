import unittest

from loaf_sizzler.storage.memory import MemoryStorage


class RegistrationRecoveryContract:
    def __init__(self):
        self.storage = MemoryStorage()
        self._profile_id = None
        self._wallet_address = "0xabc"
        self.config = type("Config", (), {"wallet_address": "0xabc"})()
        self.lookup_inputs = []

    def get_profile_by_address(self, address=None):
        lookup_address = address or self._wallet_address or (self.config.wallet_address if self.config else None)
        self.lookup_inputs.append({"addr": lookup_address} if lookup_address else {})
        return {"exists": True, "id": 42}

    def _register(self):
        raise RuntimeError("Contract call failed: AlreadyRegistered")

    from loaf_sizzler.contract_client import ContractClient
    _ensure_registered = ContractClient._ensure_registered


class RegistrationRecoveryTest(unittest.TestCase):
    def test_already_registered_uses_existing_profile(self):
        contract = RegistrationRecoveryContract()

        profile_id = contract._ensure_registered()

        self.assertEqual(profile_id, 42)
        self.assertEqual(contract.storage.get_agent_data("profile_id"), "42")
        self.assertEqual(contract.lookup_inputs[-1], {"addr": "0xabc"})


if __name__ == "__main__":
    unittest.main()
