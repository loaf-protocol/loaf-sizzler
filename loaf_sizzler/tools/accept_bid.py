def accept_bid(args: dict, axl, contract) -> dict:
    result = contract.accept_bid(
        job_id=args["job_id"],
        worker_profile_id=args["worker_profile_id"],
        agreed_worker_amount=args["agreed_worker_amount"]
    )
    own_key = axl.get_own_key()
    axl.send_acceptance(args["worker_axl_key"], args["job_id"], own_key)
    return result
