"""Compatibility layer that re-exports the renamed backtesting engine."""

from backtest_engine import *  # noqa: F401,F403

# Re-export public names for static analyzers and introspection tools.
__all__ = [name for name in globals() if not name.startswith("_")]
