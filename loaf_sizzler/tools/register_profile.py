def register_profile(args: dict, contract) -> dict:
    axl_key = args.get("axlPublicKey") or contract.axl_client.get_own_key()
    result = contract.register_profile(axl_key)
    if result.get("error"):
        return result

    profile_id = result.get("profileId")
    return {"status": "registered", "profile_id": profile_id}
