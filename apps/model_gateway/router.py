import re
from collections.abc import Mapping
from dataclasses import dataclass

from packages.model_clients.contracts import ModelProvider

from .errors import ModelNotConfigured

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class ModelRoute:
    """Maps one logical model name to a provider adapter and upstream model name."""

    provider: ModelProvider
    provider_model: str


class ModelRouter:
    """Static logical routing with no dynamic discovery or vendor SDK imports."""

    def __init__(self, routes: Mapping[str, ModelRoute]) -> None:
        validated: dict[str, ModelRoute] = {}
        for logical_model, route in routes.items():
            self._check_name(logical_model, "logical model")
            self._check_name(route.provider_model, "provider model")
            validated[logical_model] = route
        self._routes = validated

    @staticmethod
    def _check_name(value: str, label: str) -> None:
        if not _NAME.fullmatch(value):
            raise ValueError(f"invalid {label} name")

    def resolve(self, logical_model: str) -> ModelRoute:
        route = self._routes.get(logical_model)
        if route is None:
            raise ModelNotConfigured(logical_model)
        return route
