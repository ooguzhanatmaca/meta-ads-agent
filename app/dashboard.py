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
from app.meta.trends import daily_series_for_range


CACHE_SCHEMA_VERSION = 3

TREND_METRICS = [
    ("roas", "ROAS"),
    ("cpa", "CPA"),
    ("spend", "Harcama"),
    ("purchases", "Satın alma"),
    ("ctr", "CTR"),
    ("cpc", "CPC"),
]


st.set_page_config(
    page_title="Meta Ads Yönetim Paneli",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=900, show_spinner=False)
def cached_dashboard_data(
    start_date: date,
    end_date: date,
    schema_version: int = CACHE_SCHEMA_VERSION,
):
    del schema_version
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


def render_creative_detail(creative, daily_ads) -> None:
    st.divider()
    st.subheader(f"Kreatif Detayı: {creative['name']}")
    score_columns = st.columns(3)
    score_columns[0].metric("Sağlık Puanı", f"{creative['health_score']}/100")
    score_columns[1].metric("Durum", creative["health_status"])
    score_columns[2].metric("Tür", creative["creative_type"])

    trend_rows = [row for row in daily_ads if row["id"] == creative["id"]]
    if trend_rows:
        trend = pd.DataFrame(trend_rows).sort_values("date")
        left, right = st.columns(2)
        left.plotly_chart(
            px.line(
                trend,
                x="date",
                y=["roas", "ctr", "frequency"],
                markers=True,
                title="Günlük ROAS, CTR ve Frekans",
                labels={"date": "Tarih", "value": "Değer", "variable": "Metrik"},
            ),
            width="stretch",
        )
        right.plotly_chart(
            px.line(
                trend,
                x="date",
                y=["spend", "cpa"],
                markers=True,
                title="Günlük Harcama ve CPA",
                labels={"date": "Tarih", "value": "TL", "variable": "Metrik"},
            ),
            width="stretch",
        )
    else:
        st.info("Bu reklam için günlük trend verisi bulunamadı.")

    if creative["creative_type"] == "Video":
        funnel = pd.DataFrame(
            {
                "Aşama": ["Başlatma", "%25", "%50", "%75", "%95"],
                "İzlenme": [
                    creative["video_plays"],
                    creative["video_p25"],
                    creative["video_p50"],
                    creative["video_p75"],
                    creative["video_p95"],
                ],
            }
        )
        st.plotly_chart(
            px.funnel(funnel, x="İzlenme", y="Aşama", title="Video İzlenme Hunisi"),
            width="stretch",
        )

    brief = creative["creative_brief"]
    st.subheader("Yeni Varyasyon Briefi")
    st.markdown(
        f"**Hook:** {brief['hook']}\n\n"
        f"**Açı:** {brief['angle']}\n\n"
        f"**Format:** {brief['format']}\n\n"
        f"**Güven unsuru:** {brief['proof']}\n\n"
        f"**CTA:** {brief['cta']}"
    )


def render_creatives(creatives, daily_ads) -> None:
    st.subheader("Kreatif Performansı")
    st.caption(
        "Görsel ve videolar, seçilen dönemdeki reklam sonuçlarına göre "
        "kural tabanlı olarak değerlendirilir."
    )
    if not creatives:
        st.info("Seçilen dönemde kreatif verisi bulunamadı.")
        return

    filters = st.columns(3)
    types = sorted({item["creative_type"] for item in creatives})
    selected_types = filters[0].multiselect(
        "Kreatif türü",
        types,
        default=types,
    )
    labels = sorted({item["creative_label"] for item in creatives})
    selected_labels = filters[1].multiselect(
        "Performans etiketi",
        labels,
        default=labels,
    )
    show_without_spend = filters[2].checkbox(
        "Harcamasız reklamları göster",
        value=False,
    )
    visible = [
        item
        for item in creatives
        if item["creative_type"] in selected_types
        and item["creative_label"] in selected_labels
        and (show_without_spend or float(item.get("spend") or 0) > 0)
    ]

    selectable = {f"{item['name']} ({item['id']})": item for item in visible}
    selected_name = st.selectbox(
        "Detaylı analiz edilecek kreatif",
        options=list(selectable),
        index=None,
        placeholder="Bir kreatif seçin",
    )
    if selected_name:
        render_creative_detail(selectable[selected_name], daily_ads)

    for start in range(0, len(visible), 3):
        columns = st.columns(3)
        for column, creative in zip(columns, visible[start : start + 3]):
            with column.container(border=True):
                if creative["thumbnail_url"]:
                    st.image(creative["thumbnail_url"], width="stretch")
                else:
                    st.info("Kreatif önizlemesi bulunamadı.")

                st.markdown(f"**{creative['name']}**")
                st.caption(
                    f"{creative['creative_type']} | {creative['status']} | "
                    f"Kreatif ID: {creative['creative_id']}"
                )
                priority = creative["creative_priority"]
                label = creative["creative_label"]
                if priority == "critical":
                    st.error(label)
                elif priority == "high":
                    st.warning(label)
                elif label == "Bu kreatif tuttu":
                    st.success(label)
                else:
                    st.info(label)

                metrics = st.columns(4)
                metrics[0].metric("Harcama", f"₺{creative['spend']:,.0f}")
                metrics[1].metric("ROAS", f"{creative['roas']:.2f}")
                metrics[2].metric("CTR", f"%{creative['ctr']:.2f}")
                metrics[3].metric("Frekans", f"{creative['frequency']:.2f}")
                st.progress(
                    creative["health_score"] / 100,
                    text=(
                        f"Kreatif sağlık puanı: {creative['health_score']}/100 "
                        f"({creative['health_status']})"
                    ),
                )
                if creative["creative_type"] == "Video":
                    st.caption(
                        f"Video başlatma: %{creative['video_hook_rate']:.2f} | "
                        f"%75 izlenme devamlılığı: %{creative['video_hold_rate']:.2f} | "
                        f"ThruPlay: {creative['video_thruplays']:,.0f}"
                    )
                st.markdown(f"**Öneri:** {creative['creative_recommendation']}")
                st.caption(creative["creative_reason"])


@st.cache_data(ttl=900, show_spinner=False)
def cached_daily_series(since: str, until: str, schema: int):
    return daily_series_for_range(since, until)


def render_trends(start_date: date, end_date: date) -> None:
    st.subheader("Günlük Trend")
    try:
        series = cached_daily_series(str(start_date), str(end_date), CACHE_SCHEMA_VERSION)
    except (MetaAPIError, ValueError) as error:
        st.error(f"Trend verisi yüklenemedi: {error}")
        return
    if len(series) < 2:
        st.info("Trend için en az 2 günlük veri gerekir. Daha geniş bir dönem seç.")
        return

    frame = pd.DataFrame(series)
    frame["date"] = pd.to_datetime(frame["date"])
    columns = st.columns(2)
    for index, (key, label) in enumerate(TREND_METRICS):
        if key not in frame:
            continue
        figure = px.line(frame, x="date", y=key, markers=True, title=label)
        figure.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=280)
        figure.update_xaxes(title=None)
        figure.update_yaxes(title=None)
        columns[index % 2].plotly_chart(figure, width="stretch")


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
            data = cached_dashboard_data(
                start_date,
                end_date,
                CACHE_SCHEMA_VERSION,
            )
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

    (
        overview,
        trend_tab,
        creatives_tab,
        campaigns_tab,
        adsets_tab,
        ads_tab,
        actions_tab,
    ) = st.tabs(
        (
            "Genel Bakış",
            "Trend",
            "Kreatifler",
            "Kampanyalar",
            "Reklam Setleri",
            "Reklamlar",
            "Öneriler",
        )
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
    with trend_tab:
        render_trends(start_date, end_date)
    with creatives_tab:
        render_creatives(
            data.get("creatives", []),
            data.get("daily_ads", []),
        )
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
