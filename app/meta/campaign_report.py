"""CLI for the read-only Meta campaign performance report."""

from app.meta.performance_report import run_report


def main() -> int:
    return run_report("campaign", "Kampanya performans raporu")


if __name__ == "__main__":
    raise SystemExit(main())
