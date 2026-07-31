"""Provider registry: model-agnostic by construction.

The engine never imports a model. Concrete adapters (dense retrievers,
late-interaction providers, embedding providers) register a factory under a
name; configuration selects names. Expected adapter names for currently
interesting model families include "denseon", "mdenseon", "lateon", and
"mlateon" — but those adapters live outside this package (optional extras),
and nothing here or in the engine depends on their existence. A future dense
retriever, a remote service, or a hardware-accelerated scorer registers the
same way and is indistinguishable to the engine.
"""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str):
        self.kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str, factory: Callable[..., T] | None = None):
        """Register a factory, usable directly or as a decorator."""
        if factory is not None:
            self._factories[name] = factory
            return factory

        def deco(fn: Callable[..., T]) -> Callable[..., T]:
            self._factories[name] = fn
            return fn

        return deco

    def create(self, name: str, **kwargs: Any) -> T:
        try:
            factory = self._factories[name]
        except KeyError:
            raise KeyError(
                f"no {self.kind} registered as {name!r}; available: {self.names()}"
            ) from None
        return factory(**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)


embedding_providers: Registry = Registry("embedding provider")
late_interaction_providers: Registry = Registry("late-interaction provider")
dense_retrievers: Registry = Registry("dense retriever")
late_interaction_retrievers: Registry = Registry("late-interaction retriever")
