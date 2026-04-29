"""Stub for the clear_inbox tool."""


def clear_inbox(args: dict, storage) -> dict:
    """Clear locally stored inbox messages."""
    storage.clear_messages()
    return {"status": "cleared"}
