import hashlib


def get_output(args: dict, contract, storage, caller_id: str) -> dict:
   job_id = args["job_id"]
    
   # auth check — is caller an assigned verifier?
   if caller_id:
      # get caller's profile to find their profileId
      profile = contract.get_profile_by_address_or_axl_key(caller_id)
      if profile:
         is_assigned = contract.is_assigned_verifier(
            job_id, profile["id"]
         )
         if not is_assigned:
            return {"error": "unauthorized"}
    
   # get stored output
   output_record = storage.get_output(job_id)
   if not output_record:
      return {"error": "output not found"}

   if isinstance(output_record, dict):
      output = output_record.get("output")
      stored_hash = output_record.get("output_hash")
   else:
      output = output_record
      stored_hash = None
    
   # verify hash matches onchain
   computed_hash = "0x" + hashlib.sha256(output.encode()).digest().hex()
   job = contract.get_job(job_id)
   onchain_hash = job.get("outputHash")
    
   if onchain_hash and computed_hash != onchain_hash:
      return {"error": "output tampered"}
    
   return {"output": output, "output_hash": computed_hash}
