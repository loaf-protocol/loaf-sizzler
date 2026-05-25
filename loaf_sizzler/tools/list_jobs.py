def list_jobs(args: dict, contract) -> dict:
    jobs = contract.list_jobs(args.get("state"))
    if isinstance(jobs, dict) and jobs.get("error"):
        return jobs
    return {"jobs": jobs}
