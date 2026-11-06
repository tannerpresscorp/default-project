"""Normalized model gateway errors. Messages exclude prompts, outputs and provider details."""


class ModelGatewayError(Exception):
    """Base class for denied or failed model access."""


class ModelNotConfigured(ModelGatewayError):
    def __init__(self, logical_model: str) -> None:
        self.logical_model = logical_model
        super().__init__(f"model {logical_model} is not configured")


class ModelTimeout(ModelGatewayError):
    def __init__(self, logical_model: str, timeout_seconds: float) -> None:
        self.logical_model = logical_model
        self.timeout_seconds = timeout_seconds
        super().__init__(f"model {logical_model} timed out after {timeout_seconds} seconds")


class ModelProviderError(ModelGatewayError):
    def __init__(self, logical_model: str) -> None:
        self.logical_model = logical_model
        super().__init__(f"model {logical_model} failed")
