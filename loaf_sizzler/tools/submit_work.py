import hashlib


def submit_work(args: dict, storage, keeperhub) -> dict:
    """
    Worker submits completed work.
    
    args: { job_id, output }
    
    1. get output and job_id from args
    2. hash the output using sha256
       output_hash = hashlib.sha256(output.encode()).hexdigest()
   3. store output locally via storage.store_output(job_id, output, output_hash)
    4. contract write via keeperhub is TODO — needs contract
       # TODO: keeperhub.submit_work(job_id, output_hash)
    5. return { "status": "submitted", "output_hash": output_hash }
    """
    job_id = args.get("job_id")
    output = args.get("output")
    
    # Hash the output
    output_hash = hashlib.sha256(output.encode()).hexdigest()
    
   # Store output locally
   storage.store_output(job_id, output, output_hash)
    
    # TODO: keeperhub.submit_work(job_id, output_hash)
    
    return {"status": "submitted", "output_hash": output_hash}
