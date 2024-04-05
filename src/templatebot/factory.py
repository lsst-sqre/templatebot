"""Factory for templatebot services and other components."""

from dataclasses import dataclass
from typing import Self

from httpx import AsyncClient
from structlog.stdlib import BoundLogger

__all__ = ["Factory", "ProcessContext"]


@dataclass(kw_only=True, frozen=True, slots=True)
class ProcessContext:
    """Holds singletons in the context of a Ook process, which might be a
    API server or a CLI command.
    """

    http_client: AsyncClient
    """Shared HTTP client."""

    @classmethod
    async def create(cls) -> Self:
        """Create a new process context."""
        http_client = AsyncClient()

        return cls(http_client=http_client)

    async def aclose(self) -> None:
        """Close any resources held by the context."""
        await self.http_client.aclose()


class Factory:
    """Factory for Squarebot services and other components."""

    def __init__(
        self,
        *,
        logger: BoundLogger,
        process_context: ProcessContext,
    ) -> None:
        self._process_context = process_context
        self._logger = logger

    def set_logger(self, logger: BoundLogger) -> None:
        """Reset the logger for the factory.

        This is typically used by the ConsumerContext when values are bound
        to the logger.

        Parameters
        ----------
        logger
            The new logger to use.
        """
        self._logger = logger
