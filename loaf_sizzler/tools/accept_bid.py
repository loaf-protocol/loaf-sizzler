"""Stub for the accept_bid tool."""


def accept_bid(args: dict, axl, contract) -> dict:
    """Poster accepts a worker's bid."""
    own_key = axl.get_own_key()
    axl.send_acceptance(args.get("bidder_axl_key"), args.get("job_id"), own_key)
    return {"status": "accepted"}
