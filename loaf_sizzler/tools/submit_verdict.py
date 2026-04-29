"""Stub for the submit_verdict tool."""


def submit_verdict(args: dict, axl, contract) -> dict:
    """Verifier submits verdict to poster."""
    own_key = axl.get_own_key()
    axl.send_verdict(args.get("poster_axl_key"), args.get("job_id"), args.get("verdict"), args.get("reason"))
    return {"status": "verdict_sent"}
