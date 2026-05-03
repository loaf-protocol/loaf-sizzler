def get_reputation(args: dict, contract) -> dict:
    return contract.get_reputation(args["profile_id"])
