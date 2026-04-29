from .base import BaseStorage


class MemoryStorage(BaseStorage):
    def __init__(self):
        self._inbox: list = []
        self._outputs: dict = {}

    def add_message(self, message: dict) -> None:
        self._inbox.append(message)

    def get_messages(self) -> list:
        return list(self._inbox)

    def clear_messages(self) -> None:
        self._inbox.clear()

    def get_messages_by_type(self, message_type: str) -> list:
        return [message for message in self._inbox if message.get("type") == message_type]

    def store_output(self, job_id: str, output: str, output_hash: str) -> None:
        self._outputs[job_id] = {"output": output, "output_hash": output_hash}

    def get_output(self, job_id: str) -> dict | None:
        output = self._outputs.get(job_id)
        if output is None:
            return None
        return dict(output)

    def delete_output(self, job_id: str) -> None:
        self._outputs.pop(job_id, None)

    def has_output(self, job_id: str) -> bool:
        return job_id in self._outputs