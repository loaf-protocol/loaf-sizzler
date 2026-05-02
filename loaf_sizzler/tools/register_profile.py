"""Tool for explicit profile registration."""


def register_profile(args: dict, contract) -> dict:
    """
    Explicit registration tool.
    Agent can call this directly if they want.
    contract._ensure_registered()
    return { "status": "registered", "profile_id": ... }
    """
    profile_id = contract._ensure_registered()
    return {"status": "registered", "profile_id": profile_id}
