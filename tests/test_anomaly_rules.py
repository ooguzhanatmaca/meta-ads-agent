from app.meta.anomaly_report import format_alerts
from app.rules.anomaly_rules import (
    Alert,
    detect_account_anomalies,
    detect_entity_anomalies,
    detect_pacing_anomaly,
    sort_alerts,
)


def test_cpa_spike_is_flagged() -> None:
    current = {"cpa": 650, "roas": 5.0}
    previous = {"cpa": 400, "roas": 5.0}
    alerts = detect_account_anomalies(current, previous)
    assert any("CPA" in a.message for a in alerts)
    assert all(a.severity == "high" for a in alerts)


def test_roas_drop_is_flagged() -> None:
    current = {"cpa": 400, "roas": 3.0}
    previous = {"cpa": 400, "roas": 5.0}
    alerts = detect_account_anomalies(current, previous)
    assert any("ROAS" in a.message and "düştü" in a.message for a in alerts)


def test_roas_floor_is_flagged() -> None:
    alerts = detect_account_anomalies({"cpa": 400, "roas": 1.4}, {"cpa": 400, "roas": 1.5})
    assert any("eşiğinin altında" in a.message for a in alerts)


def test_stable_account_has_no_alerts() -> None:
    current = {"cpa": 410, "roas": 5.7}
    previous = {"cpa": 400, "roas": 5.6}
    assert detect_account_anomalies(current, previous) == []


def test_zero_sale_spend_flagged() -> None:
    rows = [{"name": "Reklam A", "spend": 800, "purchases": 0, "roas": 0, "frequency": 1.5}]
    alerts = detect_entity_anomalies(rows)
    assert any("satın alma yok" in a.message for a in alerts)


def test_creative_fatigue_flagged() -> None:
    rows = [{"name": "Reklam B", "spend": 600, "purchases": 5, "roas": 4, "frequency": 4.2}]
    alerts = detect_entity_anomalies(rows)
    assert any("Frekans" in a.message for a in alerts)


def test_low_frequency_not_flagged() -> None:
    rows = [{"name": "Reklam C", "spend": 600, "purchases": 5, "roas": 4, "frequency": 2.0}]
    alerts = detect_entity_anomalies(rows)
    assert alerts == []


def test_pacing_overspend_flagged() -> None:
    # Bugün 3000, 7 günlük ortalama günlük 1000 → %200 üzeri.
    alerts = detect_pacing_anomaly({"spend": 3000}, {"spend": 7000}, window_days=7)
    assert any("temposu" in a.name for a in alerts)


def test_format_alerts_all_clear() -> None:
    assert "sorun" in format_alerts([]).lower()


def test_format_and_sort() -> None:
    alerts = sort_alerts(
        [
            Alert("medium", "Reklam", "B", "frekans yüksek"),
            Alert("high", "Hesap", "A", "cpa arttı"),
        ]
    )
    assert alerts[0].severity == "high"
    text = format_alerts(alerts)
    assert "2 uyarı" in text
