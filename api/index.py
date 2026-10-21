import sys
from pathlib import Path

# Add project root directory to Python module search path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from library_app import create_app

app = create_app()
