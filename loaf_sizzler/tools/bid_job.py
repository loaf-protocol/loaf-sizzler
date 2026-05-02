"""Stub for the bid_job tool."""


def bid_job(args: dict, axl, contract) -> dict:
    """Send a bid to the poster agent over AXL."""
    contract._ensure_registered()
    own_key = axl.get_own_key()
    axl.send_bid(
        args.get("poster_axl_key"),
        args.get("job_id"),
        own_key,
        args.get("proposed_amount"),
    )
    return {"status": "bid_sent"}
