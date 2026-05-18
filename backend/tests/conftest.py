"""
conftest.py — pre-mocks heavy optional GCP dependencies so tests can be run
without google-cloud-compute / google-api-python-client installed.

IMPORTANT: We only stub modules that genuinely aren't present.
We specifically avoid overwriting "google" or "google.oauth2" if they
are already real (the generativeai SDK installs them).
"""

from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import MagicMock


BACKEND_ROOT = Path(__file__).resolve().parents[1]
backend_root_str = str(BACKEND_ROOT)
if backend_root_str not in sys.path:
    sys.path.insert(0, backend_root_str)


def _stub(name: str) -> MagicMock:
    """Create a lightweight MagicMock that looks like a module."""
    mod = MagicMock(spec=ModuleType)
    mod.__name__ = name
    mod.__spec__ = MagicMock()
    return mod


def _ensure_stub(mod_name: str, mock: MagicMock) -> None:
    """Insert mock into sys.modules only when the real module doesn't exist."""
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except (ImportError, ModuleNotFoundError):
            sys.modules[mod_name] = mock


_compute_v1 = _stub("google.cloud.compute_v1")
for _cls in (
    "InstancesClient",
    "DisksClient",
    "AddressesClient",
    "SnapshotsClient",
    "ListSnapshotsRequest",
    "AggregatedListInstancesRequest",
    "AggregatedListDisksRequest",
    "AggregatedListAddressesRequest",
):
    setattr(_compute_v1, _cls, MagicMock())

_google_cloud = _stub("google.cloud")
_google_cloud.compute_v1 = _compute_v1

_ensure_stub("google.cloud", _google_cloud)
_ensure_stub("google.cloud.compute_v1", _compute_v1)

if "google.cloud" in sys.modules and not hasattr(sys.modules["google.cloud"], "compute_v1"):
    sys.modules["google.cloud"].compute_v1 = _compute_v1  # type: ignore[attr-defined]

_discovery = _stub("googleapiclient.discovery")
_discovery.build = MagicMock(return_value=MagicMock())
_googleapiclient = _stub("googleapiclient")
_googleapiclient.discovery = _discovery

_ensure_stub("googleapiclient", _googleapiclient)
_ensure_stub("googleapiclient.discovery", _discovery)
_ensure_stub("googleapiclient.http", _stub("googleapiclient.http"))
_ensure_stub("googleapiclient.errors", _stub("googleapiclient.errors"))

_sa_creds = MagicMock()
_sa_creds.from_service_account_info = MagicMock(return_value=MagicMock())

if "google.oauth2" not in sys.modules:
    _oauth2 = _stub("google.oauth2")
    _sa = _stub("google.oauth2.service_account")
    _sa.Credentials = _sa_creds
    _oauth2.service_account = _sa
    _ensure_stub("google.oauth2", _oauth2)
    _ensure_stub("google.oauth2.service_account", _sa)
else:
    import google.oauth2.service_account as _real_sa  # noqa: F401
