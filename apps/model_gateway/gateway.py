import asyncio

from packages.model_clients.contracts import ModelRequest, ModelResponse

from .errors import ModelGatewayError, ModelProviderError, ModelTimeout
from .router import ModelRouter


class ModelGateway:
    """Route logical model requests through one governed, provider-neutral boundary."""

    def __init__(self, router: ModelRouter, *, timeout_seconds: float = 10.0) -> None:
        if not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be greater than 0 and at most 60")
        self._router = router
        self._timeout_seconds = timeout_seconds

    async def generate(self, logical_model: str, request: ModelRequest) -> ModelResponse:
        route = self._router.resolve(logical_model)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await route.provider.generate(route.provider_model, request)
        except TimeoutError as error:
            raise ModelTimeout(logical_model, self._timeout_seconds) from error
        except ModelGatewayError:
            raise
        except Exception:
            raise ModelProviderError(logical_model) from None
        if not isinstance(response, ModelResponse):
            raise ModelProviderError(logical_model)
        return response
