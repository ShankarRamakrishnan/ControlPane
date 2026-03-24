from abc import abstractmethod
from langchain_core.tools import BaseTool as LCBaseTool


class ControlPaneTool(LCBaseTool):
    """
    Base class for all ControlPane tools.
    Extend this and register via tool_registry.register().
    """

    @abstractmethod
    def _run(self, *args, **kwargs) -> str:
        ...

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)
