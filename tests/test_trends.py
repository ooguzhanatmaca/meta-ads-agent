from datetime import date
from unittest.mock import patch

from app.meta import trends


def test_sparkline_basic() -> None:
    assert trends.sparkline([1, 2, 3, 4]) != ""
    # Sabit seri en düşük karakteri verir.
    assert set(trends.sparkline([5, 5, 5])) == {trends.SPARK_CHARS[0]}
    assert trends.sparkline([]) == ""


def test_sparkline_endpoints() -> None:
    spark = trends.sparkline([0, 10])
    assert spark[0] == trends.SPARK_CHARS[0]
    assert spark[-1] == trends.SPARK_CHARS[-1]


def test_summarize_metric_higher_is_better_improving() -> None:
    series = [{"roas": 2.0}, {"roas": 2.0}, {"roas": 5.0}, {"roas": 5.0}]
    summary = trends.summarize_metric(series, "roas")
    assert summary is not None
    assert "iyileşiyor" in summary["verdict"]
    assert summary["change"] > 0


def test_summarize_metric_lower_is_better_worsening() -> None:
    # CPA artışı kötüdür.
    series = [{"cpa": 300}, {"cpa": 300}, {"cpa": 600}, {"cpa": 600}]
    summary = trends.summarize_metric(series, "cpa")
    assert "kötüleşiyor" in summary["verdict"]


def test_summarize_metric_needs_two_points() -> None:
    assert trends.summarize_metric([{"roas": 3.0}], "roas") is None


def test_build_trend_report_overview() -> None:
    fake_series = [
        {"roas": 4, "cpa": 400, "spend": 1000, "purchases": 10},
        {"roas": 5, "cpa": 380, "spend": 1100, "purchases": 12},
        {"roas": 6, "cpa": 350, "spend": 1200, "purchases": 14},
    ]
    with patch.object(trends, "daily_series", return_value=fake_series):
        out = trends.build_trend_report("özet", 3)
    assert "ROAS" in out and "CPA" in out
    assert "Trend özeti" in out


def test_build_trend_report_single_metric() -> None:
    fake_series = [{"roas": 4}, {"roas": 5}, {"roas": 6}]
    with patch.object(trends, "daily_series", return_value=fake_series):
        out = trends.build_trend_report("roas", 3)
    assert "ROAS trendi" in out


def test_build_trend_report_insufficient_data() -> None:
    with patch.object(trends, "daily_series", return_value=[{"roas": 4}]):
        assert "yeterli" in trends.build_trend_report("roas", 1)


def test_date_range() -> None:
    start, end = trends._date_range(7, date(2026, 6, 13))
    assert str(start) == "2026-06-07"
    assert str(end) == "2026-06-13"
