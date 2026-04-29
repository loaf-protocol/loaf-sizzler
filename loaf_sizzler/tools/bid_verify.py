"""Stub for the bid_verify tool."""


def bid_verify(args: dict, axl) -> dict:
    """Verifier sends a bid to poster."""
    own_key = axl.get_own_key()
    axl.send_verify_bid(args.get("poster_axl_key"), args.get("job_id"), own_key)
    return {"status": "bid_sent"}
