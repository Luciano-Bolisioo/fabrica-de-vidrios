"""Checkpointer compartido — memoria de hilo en RAM."""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver


@lru_cache
def get_checkpointer() -> InMemorySaver:
    return InMemorySaver()
