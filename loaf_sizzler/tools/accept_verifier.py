"""Stub for the accept_verifier tool."""


def accept_verifier(args: dict, axl, contract) -> dict:
    """Poster accepts a verifier's bid."""
    own_key = axl.get_own_key()
    axl.send_verifier_acceptance(args.get("verifier_axl_key"), args.get("job_id"), args.get("worker_axl_key"))
    return {"status": "accepted"}
