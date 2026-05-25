def list_review_jobs(args: dict, contract) -> dict:
    jobs = contract.list_review_jobs()
    if isinstance(jobs, dict) and jobs.get("error"):
        return jobs
    return {"jobs": jobs}
