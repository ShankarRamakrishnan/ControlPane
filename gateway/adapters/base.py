from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Contract all output adapters must implement."""

    @abstractmethod
    async def deliver(self, payload: dict[str, Any], config: dict[str, Any]) -> None:
        """Deliver a payload to the target system described by config."""
