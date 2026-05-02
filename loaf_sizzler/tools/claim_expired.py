"""Tool for claiming expired jobs."""


def claim_expired(args: dict, contract) -> dict:
    """Claim an expired job as poster."""
    tx = contract.claim_expired(args.get("job_id"))
    return {"status": "claimed", "tx_hash": tx.get("tx_hash") if isinstance(tx, dict) else None, **(tx if isinstance(tx, dict) else {})}
