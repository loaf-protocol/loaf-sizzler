"""Stub for the accept_bid tool."""


def accept_bid(args: dict, axl, contract) -> dict:
    """Poster accepts a worker's bid."""
    tx = contract.accept_bid(
        args.get("job_id"),
        args.get("worker_profile_id"),
        args.get("agreed_worker_amount"),
    )
    own_key = axl.get_own_key()
    axl.send_acceptance(args.get("worker_axl_key"), args.get("job_id"), own_key)
    return {"status": "accepted", "tx_hash": tx.get("tx_hash") if isinstance(tx, dict) else None}
