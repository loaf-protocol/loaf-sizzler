def submit_verdict(args: dict, axl, contract) -> dict:
    result = contract.submit_verdict(
        job_id=args["job_id"],
        passed=args["verdict"] == "pass"
    )
    # notify poster via AXL
    own_key = axl.get_own_key()
    axl.send_verdict(
        args["poster_axl_key"],
        args["job_id"],
        args["verdict"],
        args.get("reason", "")
    )
    return result
