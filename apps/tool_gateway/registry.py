from collections.abc import Iterable
from typing import Any, Protocol

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from packages.schemas.tools import ToolDefinition


class Tool(Protocol):
    """An in-process tool implementation. Real adapters are added in later increments."""

    definition: ToolDefinition

    async def invoke(self, arguments: dict[str, Any]) -> Any: ...


class ToolRegistry(Protocol):
    def get(self, name: str) -> Tool | None: ...

    def definitions(self) -> tuple[ToolDefinition, ...]: ...


class InMemoryToolRegistry:
    """Registration-time validated registry with no dynamic discovery or network access."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(f"tool {name} is already registered")
        if tool.definition.input_schema.get("type") != "object":
            raise ValueError(f"tool {name} input schema must describe an object")
        try:
            Draft202012Validator.check_schema(tool.definition.input_schema)
        except SchemaError as error:
            raise ValueError(f"tool {name} has an invalid input schema") from error
        self._tools[name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        definitions = (tool.definition for tool in self._tools.values())
        return tuple(sorted(definitions, key=lambda definition: definition.name))
