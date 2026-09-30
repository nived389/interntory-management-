import sys
from pathlib import Path

# Add project root directory to sys.path so app and its dependencies can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as _app_module

app = _app_module.app
application = _app_module.app
