"""CLI for the read-only Meta ad performance report."""

from app.meta.performance_report import run_report


def main() -> int:
    return run_report("ad", "Reklam performans raporu")


if __name__ == "__main__":
    raise SystemExit(main())
