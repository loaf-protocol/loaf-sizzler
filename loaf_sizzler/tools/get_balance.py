"""Stub for the get_balance tool."""


def get_balance(args: dict, contract) -> dict:
    """Read wallet balances and locked funds."""
    return contract.get_balance()
