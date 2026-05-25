"""Tool for verifiers to send a verdict over AXL."""


def verify_output(args: dict, axl) -> dict:
    """Send a verdict over AXL."""
    return axl.send_verdict(
        poster_axl_key=args["poster_axl_key"],
        job_id=args["job_id"],
        verdict=args["verdict"],
        reason=args.get("reason", "")
    )
