"""Stub for the bid_job tool."""


def bid_job(args: dict, axl) -> dict:
    """Send a bid to the poster agent over AXL."""
    own_key = axl.get_own_key()
    axl.send_bid(args.get("poster_axl_key"), args.get("job_id"), own_key)
    return {"status": "bid_sent"}
