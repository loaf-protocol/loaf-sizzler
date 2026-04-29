"""In-memory storage for inbox and output state."""


class Storage:
    """Simple in-memory storage for loaf-sizzler inbox and outputs."""

    def __init__(self):
        """Initialize empty inbox and outputs."""
        self.inbox: list = []
        self.outputs: dict = {}

    def add_message(self, message: dict) -> None:
        """Add an incoming AXL message to the inbox."""
        self.inbox.append(message)

    def get_messages(self) -> list:
        """Return all messages in the inbox."""
        return self.inbox

    def clear_messages(self) -> None:
        """Clear all messages from the inbox."""
        self.inbox = []

    def get_messages_by_type(self, message_type: str) -> list:
        """Filter inbox messages by type."""
        return [msg for msg in self.inbox if msg.get("type") == message_type]

    def store_output(self, job_id: str, output: str) -> None:
        """Store worker output for a job."""
        self.outputs[job_id] = output

    def get_output(self, job_id: str) -> str | None:
        """Retrieve output for a job_id, or None if not found."""
        return self.outputs.get(job_id)

    def delete_output(self, job_id: str) -> None:
        """Delete output after job is settled."""
        if job_id in self.outputs:
            del self.outputs[job_id]

    def has_output(self, job_id: str) -> bool:
        """Check if output exists for a job_id."""
        return job_id in self.outputs
