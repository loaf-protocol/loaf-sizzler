"""Tool for rotating the on-chain AXL key."""


def update_axl_key(args: dict, contract) -> dict:
    """Update the profile AXL key."""
    tx = contract.update_axl_key(args.get("new_key"))
    return {"status": "updated", "tx_hash": tx.get("tx_hash") if isinstance(tx, dict) else None, **(tx if isinstance(tx, dict) else {})}
