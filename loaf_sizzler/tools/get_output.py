import hashlib


def get_output(args: dict, contract, storage, caller_id: str) -> dict:
    job_id = args["job_id"]
    verifier_profile_id = args["verifier_profile_id"]

    if not caller_id:
        return {"error": "unauthorized: missing caller identity"}

    profile = contract.get_profile(verifier_profile_id)
    if not profile or profile.get("error"):
        return {"error": "unauthorized: verifier profile not found"}

    profile_axl_key = profile.get("axlPublicKey") or profile.get("axlKey") or profile.get("axl_key")
    if not profile_axl_key:
        return {"error": "unauthorized: verifier profile has no AXL key"}

    if profile_axl_key != caller_id:
        return {"error": "unauthorized: caller AXL key does not match verifier profile"}

    is_assigned = contract.is_assigned_verifier(job_id, verifier_profile_id)
    if not is_assigned:
        return {"error": "unauthorized: caller is not an assigned verifier"}

    output_record = storage.get_output(job_id)
    if not output_record:
        return {"error": "output not found"}

    if isinstance(output_record, dict):
        output = output_record.get("output")
    else:
        output = output_record

    computed_hash = "0x" + hashlib.sha256(output.encode()).digest().hex()
    job = contract.get_job(job_id)
    onchain_hash = job.get("outputHash")

    if onchain_hash and computed_hash != onchain_hash:
        return {"error": "output tampered"}

    return {"output": output, "output_hash": computed_hash}
