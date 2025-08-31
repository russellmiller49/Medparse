# scripts/linking/__init__.py
"""Entity linking module for medical concept extraction."""

from .types import VALID_TUIS, MIN_SCORE
from .linker_router import link_entities

__all__ = ["VALID_TUIS", "MIN_SCORE", "link_entities"]