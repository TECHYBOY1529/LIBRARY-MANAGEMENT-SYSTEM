import sys
from pathlib import Path

# Add project root directory to Python module search path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure runtime environment defaults are configured before Flask initializes
from scripts.auto_deploy_start import prepare_environment
prepare_environment()

from library_app import create_app

# Top-level Flask application instance for Vercel Serverless WSGI detection
app = create_app()
