import sys
import traceback
from pathlib import Path

# Add project root directory to Python module search path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from scripts.auto_deploy_start import prepare_environment
    prepare_environment()
except Exception as prep_err:
    print(f"[VERCEL BOOT] Notice during prepare_environment: {prep_err}")

try:
    from library_app import create_app
    from library_app.extensions import db
    from library_app.models import User
    from library_app.seed import seed_demo

    app = create_app()

    with app.app_context():
        try:
            db.create_all()
            if not User.query.filter_by(role="admin").first():
                seed_demo()
        except Exception as seed_err:
            app.logger.warning(f"Vercel DB initialization notice: {seed_err}")

except Exception as boot_err:
    from flask import Flask, jsonify

    app = Flask(__name__)
    err_trace = traceback.format_exc()

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def diagnostic_fallback(path):
        return jsonify({
            "status": "error",
            "message": "Application failed to initialize in Vercel Serverless environment.",
            "error": str(boot_err),
            "traceback": err_trace.splitlines()[-10:]
        }), 500
