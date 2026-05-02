"""Stub for the list_jobs tool."""


def list_jobs(args: dict, contract) -> dict:
    """Read open jobs from the contract."""
    return {"jobs": contract.list_jobs()}
