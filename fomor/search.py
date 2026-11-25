"""Pluggable search provider interface.

The MVP ships with a null provider; real providers (web search, GitHub, papers)
can implement :class:`SearchProvider` without touching the pipeline.
"""

from __future__ import annotations


class SearchProvider:
    name = "base"

    def search(self, query: str, limit: int = 5) -> list[dict]:
        raise NotImplementedError


class NullSearchProvider(SearchProvider):
    name = "none"

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return []


def build_search(settings: dict) -> SearchProvider:
    provider = settings.get("search", {}).get("provider", "none")
    if provider in ("none", "", None):
        return NullSearchProvider()
    raise ValueError(f"unsupported search provider: {provider} (MVP only ships 'none')")
