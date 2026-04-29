"""Inbound receive_message tool for loaf-sizzler."""


def receive_message(args: dict, storage) -> dict:
    """Receive an inbound AXL message and store it locally."""
    message_type = args.get("type")
    allowed_types = {
        "bid",
        "acceptance",
        "verify_bid",
        "verifier_acceptance",
        "settlement",
    }

    if not message_type or message_type not in allowed_types:
        return {"error": "invalid message type"}

    storage.add_message(args)
    return {"status": "received"}