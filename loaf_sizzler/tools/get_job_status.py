"""Stub for the get_job_status tool."""


def get_job_status(args: dict, contract) -> dict:
    """Read status for a specific job from the contract."""
    job_id = args.get("job_id")
    job = contract.get_job(job_id)
    if not isinstance(job, dict):
        return {"job_id": job_id, "status": None}
    return {
        "job_id": job_id,
        "status": job.get("state"),
        **job,
    }
