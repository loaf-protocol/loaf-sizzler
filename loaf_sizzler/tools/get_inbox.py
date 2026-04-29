"""Stub for the get_inbox tool."""


def get_inbox(args: dict, storage) -> dict:
    """Read locally stored inbox messages."""
    return {"messages": storage.get_messages()}
