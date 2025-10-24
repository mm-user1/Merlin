"""Compatibility shim for legacy imports.

This module re-exports the Flask application from ``server.py`` so that
existing commands such as ``python app.py`` or ``flask --app app run``
continue to work after the project entrypoint rename.
"""

from server import app


if __name__ == "__main__":  # pragma: no cover - convenience entrypoint
    app.run(host="0.0.0.0", port=8000, debug=False)
