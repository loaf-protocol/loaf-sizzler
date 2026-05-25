"""Stub for the get_inbox tool."""


def get_inbox(args: dict, storage) -> dict:
    """Read locally stored inbox messages."""
    message_type = args.get("type")
    if message_type:
        return {"messages": storage.get_messages_by_type(message_type)}
    return {"messages": storage.get_messages()}
