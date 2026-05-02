"""Tool for assigning verifiers to jobs."""


def assign_verifier(args: dict, axl, contract) -> dict:
    """
    args: { job_id, verifier_profile_id, verifier_axl_key, worker_axl_key }

    1. contract.assign_verifier(job_id, verifier_profile_id)
    2. axl.send_verifier_acceptance(verifier_axl_key, job_id, worker_axl_key)
    3. return { "status": "assigned", "tx_hash": ... }
    """
    tx = contract.assign_verifier(args.get("job_id"), args.get("verifier_profile_id"))
    axl.send_verifier_acceptance(
        args.get("verifier_axl_key"),
        args.get("job_id"),
        args.get("worker_axl_key"),
    )
    return {"status": "assigned", "tx_hash": tx.get("tx_hash") if isinstance(tx, dict) else None}
