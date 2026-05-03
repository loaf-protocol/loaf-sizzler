def assign_verifier(args: dict, axl, contract) -> dict:
    result = contract.assign_verifier(
        job_id=args["job_id"],
        verifier_profile_id=args["verifier_profile_id"]
    )
    # notify verifier via AXL with worker_axl_key
    own_key = axl.get_own_key()
    axl.send_verifier_acceptance(
        args["verifier_axl_key"],
        args["job_id"],
        args["worker_axl_key"]
    )
    return result
