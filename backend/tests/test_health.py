import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engine import health
from urice_engine import __version__


def test_health_payload():
    payload = health()
    assert payload["ok"] is True
    assert payload["version"] == __version__
    assert payload["engine"] == "urice-python-sidecar"
