"""
Strategy Registry - Auto-discovery system for trading strategies

This module automatically discovers all strategies in the strategies/ directory
and provides a unified interface for accessing them.
"""

import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

STRATEGIES_DIR = Path(__file__).parent
_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _discover_strategies():
    """
    Auto-discover all strategies by scanning subdirectories.

    Each strategy must have:
    - config.json (metadata and parameters)
    - strategy.py (trading logic)

    Strategies are registered in _REGISTRY dictionary.
    """
    global _REGISTRY

    for item in STRATEGIES_DIR.iterdir():
        if not item.is_dir() or item.name.startswith("_"):
            continue

        config_file = item / "config.json"
        strategy_file = item / "strategy.py"

        if not (config_file.exists() and strategy_file.exists()):
            print(f"Warning: Incomplete strategy in {item.name}, skipping")
            continue

        try:
            with config_file.open("r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {config_file}: {e}")
            continue

        strategy_id = config.get("id", item.name)

        module_name = f"strategies.{item.name}.strategy"
        try:
            module = importlib.import_module(module_name)

            strategy_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr.__module__ == module_name
                    and hasattr(attr, "run")
                    and hasattr(attr, "STRATEGY_ID")
                ):
                    strategy_class = attr
                    break

            if strategy_class is None:
                print(f"Warning: No valid strategy class found in {module_name}")
                continue

            # Attach configuration to the strategy class for downstream use
            setattr(strategy_class, "CONFIG", config)

            _REGISTRY[strategy_id] = {
                "class": strategy_class,
                "config": config,
                "path": item,
            }

        except Exception as e:  # noqa: BLE001
            print(f"Error loading strategy {item.name}: {e}")
            continue


def get_strategy(strategy_id: str):
    """
    Get strategy class by ID.

    Args:
        strategy_id: Strategy identifier (e.g., 's01_trailing_ma')

    Returns:
        Strategy class

    Raises:
        ValueError: If strategy not found
    """
    if strategy_id not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(
            f"Unknown strategy: {strategy_id}. " f"Available strategies: {available}"
        )
    return _REGISTRY[strategy_id]["class"]


def get_strategy_config(strategy_id: str) -> Dict[str, Any]:
    """
    Get strategy configuration (from config.json).

    Args:
        strategy_id: Strategy identifier

    Returns:
        Dictionary with strategy metadata and parameters

    Raises:
        ValueError: If strategy not found
    """
    if strategy_id not in _REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_id}")
    return _REGISTRY[strategy_id]["config"]


def list_strategies() -> List[Dict[str, Any]]:
    """
    List all available strategies.

    Returns:
        List of dictionaries with strategy metadata:
        [
            {
                'id': 's01_trailing_ma',
                'name': 'S01 Trailing MA',
                'version': 'v26',
                'description': '...',
                ...
            }
        ]
    """
    result = []
    for strategy_id, data in _REGISTRY.items():
        config = data["config"]
        result.append(
            {
                "id": strategy_id,
                "name": config.get("name", strategy_id),
                "version": config.get("version", "unknown"),
                "description": config.get("description", ""),
                "author": config.get("author", ""),
            }
        )
    return result


_discover_strategies()

if _REGISTRY:
    print(f"Discovered {len(_REGISTRY)} strategy(ies): {list(_REGISTRY.keys())}")
else:
    print("Warning: No strategies discovered")
