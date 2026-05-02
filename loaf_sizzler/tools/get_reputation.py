"""Stub for the get_reputation tool."""


def get_reputation(args: dict, contract) -> dict:
    """Read reputation from the contract."""
    return contract.get_reputation(args["profile_id"])
