from .base import BaseStorage
from .memory import MemoryStorage
from .sqlite import SQLiteStorage


def create_storage(backend: str = "memory", db_path: str = "loaf.db") -> BaseStorage:
    """
    Factory function.
    backend: "memory" | "sqlite"
    """
    if backend == "sqlite":
        return SQLiteStorage(db_path)
    return MemoryStorage()