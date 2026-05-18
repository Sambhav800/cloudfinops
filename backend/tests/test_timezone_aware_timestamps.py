from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _deprecated_utc_call_token() -> str:
    return "utc" + "now("


def test_target_backend_modules_do_not_use_deprecated_utc_helper() -> None:
    """Regression guard: the targeted backend modules must not reintroduce the deprecated UTC helper."""
    forbidden = _deprecated_utc_call_token()
    for relative_path in (
        "backend/app/api/routes.py",
        "backend/app/core/finance.py",
        "backend/app/scanners/aws.py",
        "backend/app/scanners/azure.py",
        "backend/app/scanners/gcp.py",
    ):
        assert forbidden not in _read(relative_path), relative_path


def test_routes_use_timezone_aware_iso_timestamps_for_health_and_scan_updates() -> None:
    source = _read("backend/app/api/routes.py")
    assert source.count("datetime.now(timezone.utc).isoformat()") >= 4


def test_finance_keeps_timezone_aware_utc_today_helper() -> None:
    source = _read("backend/app/core/finance.py")
    assert "return datetime.now(timezone.utc).date()" in source
