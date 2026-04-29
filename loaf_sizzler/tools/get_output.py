import hashlib


def get_output(args: dict, storage, contract, caller_id: str) -> dict:
    """
    PUBLIC tool — called by remote verifiers over AXL.
    Returns stored worker output for a job.
    
    args: { job_id }
    caller_id: X-From-Peer-Id header (verifier's AXL key)
    
    1. get job_id from args
    2. auth check → TODO (needs contract)
       # TODO: verify caller_id is assigned verifier via contract
       # contract.is_assigned_verifier(job_id, caller_id)
       # for now skip auth check
    
    3. get output from storage
       output = storage.get_output(job_id)
       if output is None:
           return { "error": "output not found" }
    
    4. verify output hash matches what was submitted
       computed_hash = hashlib.sha256(output.encode()).hexdigest()
       # TODO: compare against onchain hash when contract exists
       # onchain_hash = contract.get_output_hash(job_id)
       # if computed_hash != onchain_hash:
       #     return { "error": "output tampered" }
    
    5. return { "output": output, "output_hash": computed_hash }
    """
    job_id = args.get("job_id")
    
   # Get output from storage
   output_record = storage.get_output(job_id)
   if output_record is None:
        return {"error": "output not found"}
    
   output = output_record["output"]
   stored_hash = output_record["output_hash"]

   # Compute output hash
   computed_hash = hashlib.sha256(output.encode()).hexdigest()
    
    # TODO: verify caller_id is assigned verifier via contract
    # TODO: compare computed_hash against onchain hash
    
   if computed_hash != stored_hash:
      return {"error": "output tampered"}

   return {"output": output, "output_hash": computed_hash}
