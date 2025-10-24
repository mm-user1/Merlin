"""Legacy wrapper for the renamed CLI runner."""

from run_backtest import DEFAULT_CSV_PATH, build_default_params, main

__all__ = ["DEFAULT_CSV_PATH", "build_default_params", "main"]


if __name__ == "__main__":  # pragma: no cover - convenience entrypoint
    main()
