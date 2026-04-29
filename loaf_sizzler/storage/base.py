from abc import ABC, abstractmethod


class BaseStorage(ABC):
    @abstractmethod
    def add_message(self, message: dict) -> None:
        """Add incoming AXL message to inbox."""

    @abstractmethod
    def get_messages(self) -> list:
        """Return all messages in inbox."""

    @abstractmethod
    def clear_messages(self) -> None:
        """Clear all messages from inbox."""

    @abstractmethod
    def get_messages_by_type(self, message_type: str) -> list:
        """
        Filter inbox by message type.
        Types: bid | acceptance | verify_bid | verifier_acceptance | settlement
        """

    @abstractmethod
    def store_output(self, job_id: str, output: str, output_hash: str) -> None:
        """Store worker output and hash for a job."""

    @abstractmethod
    def get_output(self, job_id: str) -> dict | None:
        """
        Retrieve output for a job_id.
        Returns { output, output_hash } or None if not found.
        """

    @abstractmethod
    def delete_output(self, job_id: str) -> None:
        """Delete output after job is settled."""

    @abstractmethod
    def has_output(self, job_id: str) -> bool:
        """Check if output exists for a job_id."""