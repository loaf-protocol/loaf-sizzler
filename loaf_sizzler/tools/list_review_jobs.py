"""Stub for the list_review_jobs tool."""


def list_review_jobs(args: dict, contract) -> dict:
    """Read in-review jobs from the contract."""
    return {"jobs": contract.list_review_jobs()}
