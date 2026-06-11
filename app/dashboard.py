"""Local Streamlit dashboard for read-only Meta Ads analysis."""

from datetime import date, timedelta
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.dashboard_data import (
    dashboard_excel_bytes,
    load_dashboard_data,
    recommendations_dataframe,
    rows_to_dataframe,
)
from app.meta.client import MetaAPIError


st.set_page_config(
    page_title="Meta Ads Yönetim Paneli",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=900, show_spinner=False)
def cached_dashboard_data(start_date: date, end_date: date):
    return load_dashboard_data(start_date, end_date)


def metric_delta(comparison, metric: str, inverse: bool = False) -> str:
    item = next(row for row in comparison if row["metric"] == metric)
    change = item["change"]
    if inverse:
        change *= -1
    return f"{change:+.1f}%"


def render_kpis(data) -> None:
    metrics = data["current"]
    comparison = data["comparison"]
    first = st.columns(4)
    first[0].metric("Harcama", f"₺{metrics['spend']:,.2f}", metric_delta(comparison, "spend"))
    first[1].metric("Satış Değeri", f"₺{metrics['purchase_value']:,.2f}", metric_delta(comparison, "purchase_value"))
    first[2].metric("Satın Alma", f"{metrics['purchases']:,.0f}", metric_delta(comparison, "purchases"))
    first[3].metric("ROAS", f"{metrics['roas']:.2f}", metric_delta(comparison, "roas"))

    second = st.columns(5)
    second[0].metric("CPA", f"₺{metrics['cpa']:,.2f}", metric_delta(comparison, "cpa", inverse=True))
    second[1].metric("CTR", f"%{metrics['ctr']:.2f}", metric_delta(comparison, "ctr"))
    second[2].metric("CPC", f"₺{metrics['cpc']:,.2f}", metric_delta(comparison, "cpc", inverse=True))
    second[3].metric("CPM", f"₺{metrics['cpm']:,.2f}", metric_delta(comparison, "cpm"))
    second[4].metric("Frekans", f"{metrics['frequency']:.2f}", metric_delta(comparison, "frequency"))


def render_charts(data) -> None:
    ads = pd.DataFrame(data["ads"])
    if ads.empty:
        st.info("Seçilen dönemde grafik oluşturacak reklam verisi bulunamadı.")
        return

    left, right = st.columns(2)
    top_ads = ads.sort_values(["roas", "purchases"], ascending=False).head(10)
    left.plotly_chart(
        px.bar(
            top_ads,
            x="name",
            y="roas",
            color="spend",
            title="ROAS'a Göre En İyi Reklamlar",
            labels={"name": "Reklam", "roas": "ROAS", "spend": "Harcama"},
            color_continuous_scale="Blues",
        ),
        width="stretch",
    )
    right.plotly_chart(
        px.scatter(
            ads,
            x="frequency",
            y="ctr",
            size="spend",
            color="roas",
            hover_name="name",
            title="Frekans ve CTR İlişkisi",
            labels={"frequency": "Frekans", "ctr": "CTR (%)", "roas": "ROAS"},
            color_continuous_scale="RdYlGn",
        ),
        width="stretch",
    )


def render_table(title: str, rows, columns) -> None:
    st.subheader(title)
    frame = rows_to_dataframe(rows, columns)
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Harcama": st.column_config.NumberColumn(format="₺ %.2f"),
            "CPC": st.column_config.NumberColumn(format="₺ %.2f"),
            "CPM": st.column_config.NumberColumn(format="₺ %.2f"),
            "Satış Değeri": st.column_config.NumberColumn(format="₺ %.2f"),
            "CPA": st.column_config.NumberColumn(format="₺ %.2f"),
            "CTR": st.column_config.NumberColumn(format="%.2f%%"),
            "ROAS": st.column_config.NumberColumn(format="%.2f"),
            "Frekans": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def main() -> None:
    st.title("Meta Ads Yönetim Paneli")
    st.caption("Salt okunur analiz paneli. Meta üzerinde değişiklik yapmaz.")

    today = date.today()
    with st.sidebar:
        st.header("Rapor Ayarları")
        preset = st.selectbox(
            "Hazır dönem",
            ("Son 7 gün", "Bugün", "Son 14 gün", "Son 30 gün", "Özel"),
        )
        days = {"Bugün": 1, "Son 7 gün": 7, "Son 14 gün": 14, "Son 30 gün": 30}
        if preset == "Özel":
            start_date = st.date_input("Başlangıç", today - timedelta(days=6))
            end_date = st.date_input("Bitiş", today)
        else:
            end_date = today
            start_date = today - timedelta(days=days[preset] - 1)
        refresh = st.button("Verileri yenile", width="stretch")
        if refresh:
            cached_dashboard_data.clear()

    try:
        with st.spinner("Meta raporları yükleniyor..."):
            data = cached_dashboard_data(start_date, end_date)
    except (MetaAPIError, ValueError) as error:
        st.error(f"Panel verileri yüklenemedi: {error}")
        return

    st.caption(
        f"Dönem: {start_date} - {end_date} | "
        f"Karşılaştırma: {data['previous_start']} - {data['previous_end']}"
    )
    render_kpis(data)

    critical = [
        item
        for item in data["recommendations"]
        if item["priority"] in {"critical", "high"}
    ]
    if critical:
        st.error(f"{len(critical)} öncelikli aksiyon bulundu.")
    else:
        st.success("Kritik veya yüksek öncelikli aksiyon bulunmadı.")

    overview, campaigns_tab, adsets_tab, ads_tab, actions_tab = st.tabs(
        ("Genel Bakış", "Kampanyalar", "Reklam Setleri", "Reklamlar", "Öneriler")
    )
    common_metrics = [
        "status",
        "spend",
        "impressions",
        "reach",
        "clicks",
        "ctr",
        "cpc",
        "cpm",
        "frequency",
        "purchases",
        "purchase_value",
        "cpa",
        "roas",
    ]
    with overview:
        render_charts(data)
    with campaigns_tab:
        render_table("Kampanya Performansı", data["campaigns"], ["id", "name", *common_metrics])
    with adsets_tab:
        render_table(
            "Reklam Seti Performansı",
            data["adsets"],
            ["id", "name", "campaign_name", *common_metrics],
        )
    with ads_tab:
        render_table(
            "Reklam Performansı",
            data["ads"],
            ["id", "name", "adset_name", "campaign_name", *common_metrics],
        )
    with actions_tab:
        st.dataframe(
            recommendations_dataframe(data["recommendations"]),
            width="stretch",
            hide_index=True,
        )

    st.download_button(
        "Bu dönemi Excel olarak indir",
        data=dashboard_excel_bytes(data),
        file_name=f"meta_ads_dashboard_{start_date}_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )


if __name__ == "__main__":
    main()
