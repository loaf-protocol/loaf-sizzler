import hashlib


def submit_work(args: dict, storage, contract) -> dict:
    output = args["output"]
    job_id = args["job_id"]
    
    # hash as bytes32
    output_hash = hashlib.sha256(output.encode()).digest()
    output_hash_hex = "0x" + output_hash.hex()
    
    # store locally
    storage.store_output(job_id, output)
    
    # write onchain
    result = contract.submit_work(job_id, output_hash_hex)
    return {"status": "submitted", "output_hash": output_hash_hex, **result}
