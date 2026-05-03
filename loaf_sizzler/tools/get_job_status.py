def get_job_status(args: dict, contract) -> dict:
    job = contract.get_job(args["job_id"])
    return job
