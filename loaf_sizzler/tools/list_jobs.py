def list_jobs(args: dict, contract) -> dict:
    return {"jobs": contract.list_jobs()}
