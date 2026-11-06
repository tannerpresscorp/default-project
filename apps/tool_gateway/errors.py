"""Governed tool access errors. Messages deliberately exclude arguments and tool output."""


class ToolGatewayError(Exception):
    """Base class for denied or failed tool access."""


class ToolNotFound(ToolGatewayError):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"tool {tool_name} is not registered")


class ToolNotAllowed(ToolGatewayError):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"tool {tool_name} is not allowed for this tenant")


class ToolApprovalRequired(ToolGatewayError):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"tool {tool_name} requires approval")


class ToolValidationError(ToolGatewayError):
    def __init__(self, tool_name: str, path: tuple[str | int, ...]) -> None:
        self.tool_name = tool_name
        self.path = path
        location = ".".join(str(part) for part in path) or "<root>"
        super().__init__(f"invalid arguments for tool {tool_name} at {location}")


class ToolTimeout(ToolGatewayError):
    def __init__(self, tool_name: str, timeout_seconds: float) -> None:
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        super().__init__(f"tool {tool_name} timed out after {timeout_seconds} seconds")


class ToolExecutionError(ToolGatewayError):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"tool {tool_name} failed")
