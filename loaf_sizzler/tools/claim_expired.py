def claim_expired(args: dict, contract) -> dict:
    return contract.claim_expired(args["job_id"])
