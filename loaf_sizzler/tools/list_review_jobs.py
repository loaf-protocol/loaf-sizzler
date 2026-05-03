def list_review_jobs(args: dict, contract) -> dict:
    return {"jobs": contract.list_review_jobs()}
