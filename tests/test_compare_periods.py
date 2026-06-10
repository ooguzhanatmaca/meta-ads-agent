from datetime import date
from unittest.mock import patch

import pytest

from app.meta.compare_periods import (
    build_default_periods,
    calculate_period_metrics,
    compare_metrics,
    main,
    percentage_change,
    result_label,
)


def test_build_default_periods_uses_inclusive_non_overlapping_ranges() -> None:
    periods = build_default_periods(date(2026, 6, 11))

    assert periods[0].current_since == date(2026, 6, 11)
    assert periods[0].previous_since == date(2026, 6, 10)
    assert periods[1].current_since == date(2026, 6, 9)
    assert periods[1].previous_since == date(2026, 6, 6)
    assert periods[1].previous_until == date(2026, 6, 8)
    assert periods[2].current_since == date(2026, 6, 5)
    assert periods[2].previous_since == date(2026, 5, 29)
    assert periods[2].previous_until == date(2026, 6, 4)


def test_calculate_period_metrics_reuses_summary_and_handles_zero_reach() -> None:
    metrics = calculate_period_metrics({"spend": "100", "reach": "0"})

    assert metrics["spend"] == 100
    assert metrics["frequency"] == 0


@pytest.mark.parametrize(
    ("metric", "current", "previous", "expected"),
    (
        ("roas", 3, 2, "iyileşti"),
        ("cpa", 300, 500, "iyileşti"),
        ("ctr", 0.8, 1.2, "kötüleşti"),
        ("cpc", 5, 4, "kötüleşti"),
        ("purchases", 10, 5, "iyileşti"),
        ("spend", 2000, 1000, "nötr"),
        ("cpm", 30, 20, "nötr"),
        ("frequency", 3.6, 3.2, "kötüleşti"),
        ("frequency", 3.4, 3.8, "iyileşti"),
    ),
)
def test_result_labels(metric, current, previous, expected) -> None:
    assert result_label(metric, current, previous) == expected


def test_percentage_change_handles_zero_values() -> None:
    assert percentage_change(0, 0) == 0
    assert percentage_change(10, 0) == 100
    assert percentage_change(0, 10) == -100


def test_compare_metrics_contains_direction_change_and_result() -> None:
    comparison = compare_metrics({"roas": 4}, {"roas": 2})
    roas = next(item for item in comparison if item["metric"] == "roas")

    assert roas["change"] == 100
    assert roas["direction"] == "arttı"
    assert roas["result"] == "iyileşti"


@patch("app.meta.compare_periods.build_default_periods")
@patch("app.meta.compare_periods.get_account_insights_for_period")
def test_cli_uses_mocked_period_data(mock_get, mock_periods, capsys) -> None:
    mock_periods.return_value = build_default_periods(date(2026, 6, 11))[:1]
    mock_get.side_effect = [
        {"spend": "200", "impressions": "1000", "reach": "500"},
        {"spend": "100", "impressions": "500", "reach": "250"},
    ]

    assert main() == 0
    output = capsys.readouterr().out
    assert "Bugün vs dün" in output
    assert "iyileşti" in output or "nötr" in output
    assert "test-token" not in output
    assert mock_get.call_count == 2
