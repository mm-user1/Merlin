import sys
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from . import server_services as _services
    from .server_routes_data import register_routes as register_data_routes
    from .server_routes_run import register_routes as register_run_routes
except ImportError:
    import server_services as _services
    from server_routes_data import register_routes as register_data_routes
    from server_routes_run import register_routes as register_run_routes

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
    static_url_path="/static",
)

register_data_routes(app)
register_run_routes(app)

_build_optimization_config = _services._build_optimization_config


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
