import hashlib


def submit_work(args: dict, storage, contract) -> dict:
    """
    Worker submits completed work.
    
    args: { job_id, output }
    
    1. get output and job_id from args
    1. hash output as bytes32
       output_hash = hashlib.sha256(output.encode()).digest()
    2. store output locally
       storage.store_output(job_id, output)
    3. contract.submit_work(job_id, output_hash)
    4. return { "status": "submitted", "output_hash": output_hash.hex() }
    """
    job_id = args.get("job_id")
    output = args.get("output")

    output_hash = hashlib.sha256(output.encode()).digest()

    try:
        storage.store_output(job_id, output)
    except TypeError:
        storage.store_output(job_id, output, output_hash.hex())

    contract.submit_work(job_id, output_hash)
    return {"status": "submitted", "output_hash": output_hash.hex()}
