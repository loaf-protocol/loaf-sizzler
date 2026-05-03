def post_job(args: dict, contract) -> dict:
    return contract.post_job(
        criteria=args["criteria"],
        worker_amount=args["worker_amount"],
        verifier_fee_each=args["verifier_fee_each"],
        verifier_count=args["verifier_count"],
        quorum_threshold=args["quorum_threshold"],
        min_verifier_score=args["min_verifier_score"],
        expires_at=args["expires_at"]
    )
