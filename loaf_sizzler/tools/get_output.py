import hashlib


def get_output(args: dict, contract, storage, caller_id: str) -> dict:
   """
   PUBLIC tool — called by remote verifiers over AXL.
   Returns stored worker output for a job.

   args: { job_id }
   caller_id: X-From-Peer-Id header (verifier's AXL key)
   """
   job_id = args.get("job_id")

   output_record = storage.get_output(job_id)
   if output_record is None:
      return {"error": "output not found"}

   if isinstance(output_record, dict):
      output = output_record.get("output")
      stored_hash = output_record.get("output_hash")
   else:
      output = output_record
      stored_hash = hashlib.sha256(output.encode()).hexdigest()

   computed_hash = hashlib.sha256(output.encode()).hexdigest()

   # TODO: verify caller_id is assigned verifier via contract
   # TODO: compare computed_hash against onchain hash
   if computed_hash != stored_hash:
      return {"error": "output tampered"}

   return {"output": output, "output_hash": computed_hash}
