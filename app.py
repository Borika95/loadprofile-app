import io
import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)


# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------
st.set_page_config(
    page_title="Energieeffizienz-Check Produktion",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --primary: #0f766e;
        --primary-dark: #115e59;
        --accent: #f59e0b;
        --bg-soft: #f8fafc;
        --card: #ffffff;
        --text-muted: #64748b;
    }

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 1200px;
    }

    .hero {
        background: linear-gradient(135deg, #0f766e 0%, #134e4a 55%, #0f172a 100%);
        padding: 2.2rem 2.4rem;
        border-radius: 28px;
        color: white;
        box-shadow: 0 24px 60px rgba(15, 118, 110, 0.22);
        margin-bottom: 1.6rem;
    }

    .hero h1 {
        font-size: 2.45rem;
        margin-bottom: 0.4rem;
        line-height: 1.08;
    }

    .hero p {
        color: rgba(255, 255, 255, 0.82);
        font-size: 1.05rem;
        max-width: 780px;
    }

    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-top: 1.2rem;
    }

    .badge {
        background: rgba(255, 255, 255, 0.13);
        border: 1px solid rgba(255, 255, 255, 0.20);
        color: white;
        padding: 0.42rem 0.72rem;
        border-radius: 999px;
        font-size: 0.86rem;
    }

    .section-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 1.35rem 1.45rem;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.055);
        margin-bottom: 1rem;
    }

    .metric-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 22px;
        padding: 1rem 1.1rem;
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }

    .muted {
        color: #64748b;
    }

    .risk-high {
        color: #b91c1c;
        font-weight: 700;
    }

    .risk-medium {
        color: #b45309;
        font-weight: 700;
    }

    .risk-low {
        color: #047857;
        font-weight: 700;
    }

    div[data-testid="stProgress"] > div > div > div > div {
        background-color: #0f766e;
    }

    .stButton > button {
        border-radius: 999px;
        border: none;
        background: linear-gradient(135deg, #0f766e, #0d9488);
        color: white;
        padding: 0.7rem 1.3rem;
        font-weight: 700;
        box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
    }

    .stDownloadButton > button {
        border-radius: 999px;
        background: #0f766e;
        color: white;
        font-weight: 700;
        border: none;
        padding: 0.7rem 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Session state
# ------------------------------------------------------------
def init_state():
    defaults = {
        "step": 1,
        "company_data": {},
        "production_data": {},
        "energy_data": {},
        "process_data": {},
        "analysis": None,
        "df": None,
        "email": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def next_step():
    st.session_state.step = min(st.session_state.step + 1, 6)


def previous_step():
    st.session_state.step = max(st.session_state.step - 1, 1)


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def generate_dummy_load_profile() -> pd.DataFrame:
    rng = pd.date_range("2026-01-01 00:00", periods=7 * 24 * 4, freq="15min")
    hours = rng.hour + rng.minute / 60
    weekday = rng.weekday

    base = 72 + np.random.normal(0, 3, len(rng))
    production = np.where((weekday < 5) & (hours >= 6) & (hours <= 22), 145, 0)
    cycles = 38 * (np.sin(np.arange(len(rng)) / 5.5) > 0.35).astype(int)
    peaks = np.zeros(len(rng))
    peaks[80:90] += 55
    peaks[280:292] += 70
    power = base + production + cycles + peaks + np.random.normal(0, 5, len(rng))
    power = np.maximum(power, 35)

    return pd.DataFrame({"timestamp": rng, "power_kw": power.round(2)})


def read_load_profile(file) -> pd.DataFrame:
    if file is None:
        return generate_dummy_load_profile()

    if file.name.endswith(".xlsx"):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    lower_cols = {c.lower().strip(): c for c in df.columns}

    time_col = None
    for candidate in ["timestamp", "time", "datetime", "date", "zeit", "datum"]:
        if candidate in lower_cols:
            time_col = lower_cols[candidate]
            break

    power_col = None
    for candidate in ["power_kw", "leistung", "kw", "load", "lastgang", "power"]:
        if candidate in lower_cols:
            power_col = lower_cols[candidate]
            break

    if time_col is None:
        time_col = df.columns[0]
    if power_col is None:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        power_col = numeric_cols[0] if numeric_cols else df.columns[1]

    result = df[[time_col, power_col]].copy()
    result.columns = ["timestamp", "power_kw"]
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce")
    result["power_kw"] = pd.to_numeric(result["power_kw"], errors="coerce")
    result = result.dropna().sort_values("timestamp")

    return result


def analyze_load_profile(df: pd.DataFrame, production_data: dict, energy_data: dict) -> dict:
    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday
    df["date"] = df["timestamp"].dt.date

    median_interval_hours = df["timestamp"].diff().dt.total_seconds().dropna().median() / 3600
    if not np.isfinite(median_interval_hours) or median_interval_hours <= 0:
        median_interval_hours = 0.25

    df["energy_kwh"] = df["power_kw"] * median_interval_hours

    total_energy = df["energy_kwh"].sum()
    peak_power = df["power_kw"].max()
    base_load = df["power_kw"].quantile(0.1)
    avg_power = df["power_kw"].mean()
    load_factor = avg_power / peak_power if peak_power else 0

    threshold = df["power_kw"].rolling(8, min_periods=1).mean().quantile(0.72)
    df["production_cycle"] = df["power_kw"].rolling(8, min_periods=1).mean() > threshold

    transitions = df["production_cycle"].astype(int).diff().fillna(0)
    detected_cycles = int((transitions == 1).sum())

    non_prod = df[(df["weekday"] >= 5) | (df["hour"] < 6) | (df["hour"] > 22)]
    non_prod_energy = non_prod["energy_kwh"].sum()
    non_prod_share = non_prod_energy / total_energy if total_energy else 0

    annual_output = production_data.get("annual_output", 100000) or 100000
    energy_per_unit = total_energy / max(annual_output / 52, 1)

    price = energy_data.get("electricity_price", 0.22) or 0.22
    estimated_savings_kwh = total_energy * min(0.18, max(0.05, non_prod_share * 0.45))
    estimated_savings_eur = estimated_savings_kwh * price

    recommendations = []
    if non_prod_share > 0.22:
        recommendations.append("Grundlast außerhalb der Produktionszeiten prüfen und Abschaltkonzepte für Nebenaggregate ableiten.")
    if load_factor < 0.55:
        recommendations.append("Lastspitzen analysieren und zeitliche Entzerrung energieintensiver Prozesse prüfen.")
    if base_load > avg_power * 0.45:
        recommendations.append("Hohe Grundlast identifiziert: Druckluft, Pumpen, Absaugung, Temperierung und Standby-Verbrauch priorisieren.")
    if detected_cycles > 12:
        recommendations.append("Viele Produktionszyklen erkannt: Zyklusabhängige Energiekennzahlen je Produktgruppe aufbauen.")
    if not recommendations:
        recommendations.append("Keine ausgeprägigen Auffälligkeiten erkannt. Nächster Schritt: Feinere Segmentierung nach Linie, Produkt und Schicht.")

    return {
        "df": df,
        "total_energy": total_energy,
        "peak_power": peak_power,
        "base_load": base_load,
        "avg_power": avg_power,
        "load_factor": load_factor,
        "detected_cycles": detected_cycles,
        "non_prod_energy": non_prod_energy,
        "non_prod_share": non_prod_share,
        "energy_per_unit": energy_per_unit,
        "estimated_savings_kwh": estimated_savings_kwh,
        "estimated_savings_eur": estimated_savings_eur,
        "recommendations": recommendations,
    }


def fig_to_buffer(fig) -> io.BytesIO:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    buffer.seek(0)
    return buffer


def create_load_plot(df: pd.DataFrame) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10.5, 3.5))
    ax.plot(df["timestamp"], df["power_kw"], linewidth=1.2)
    ax.set_title("Lastgang mit Leistungsaufnahme")
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Leistung [kW]")
    ax.grid(True, alpha=0.28)
    fig.autofmt_xdate()
    buffer = fig_to_buffer(fig)
    plt.close(fig)
    return buffer


def create_pdf_report(company_data, production_data, energy_data, process_data, analysis) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="HeroTitle", fontSize=22, leading=26, spaceAfter=14, textColor=colors.HexColor("#0f766e")))
    styles.add(ParagraphStyle(name="Subtle", fontSize=9, leading=12, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle(name="Section", fontSize=14, leading=18, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#134e4a")))

    story = []
    story.append(Paragraph("Energieeffizienz-Analyse Produktion", styles["HeroTitle"]))
    story.append(Paragraph(f"Automatisch generierter Demo-Bericht vom {datetime.now().strftime('%d.%m.%Y, %H:%M')} Uhr", styles["Subtle"]))
    story.append(Spacer(1, 0.45 * cm))

    company_rows = [
        ["Unternehmen", company_data.get("company_name", "-")],
        ["Branche", company_data.get("industry", "-")],
        ["Standort", company_data.get("location", "-")],
        ["Produktionsmodell", production_data.get("shift_model", "-")],
    ]
    story.append(Paragraph("1. Kontext", styles["Section"]))
    story.append(make_table(company_rows))

    metric_rows = [
        ["Gesamtenergie im Analysezeitraum", f"{analysis['total_energy']:,.0f} kWh"],
        ["Maximale Leistung", f"{analysis['peak_power']:,.1f} kW"],
        ["Grundlast", f"{analysis['base_load']:,.1f} kW"],
        ["Lastfaktor", f"{analysis['load_factor']:.2f}"],
        ["Erkannte Produktionszyklen", f"{analysis['detected_cycles']}"] ,
        ["Energie je Einheit", f"{analysis['energy_per_unit']:.2f} kWh/Stück"],
        ["Geschätztes Einsparpotenzial", f"{analysis['estimated_savings_kwh']:,.0f} kWh / {analysis['estimated_savings_eur']:,.0f} EUR"],
    ]
    story.append(Paragraph("2. Energiekennzahlen", styles["Section"]))
    story.append(make_table(metric_rows))

    plot_buffer = create_load_plot(analysis["df"])
    story.append(Paragraph("3. Lastgang", styles["Section"]))
    story.append(Image(plot_buffer, width=16 * cm, height=5.2 * cm))

    story.append(Paragraph("4. Erste Handlungsempfehlungen", styles["Section"]))
    for rec in analysis["recommendations"]:
        story.append(Paragraph(f"• {rec}", styles["BodyText"]))
        story.append(Spacer(1, 0.12 * cm))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Hinweis: Dieser Bericht ist ein Dummy-Beispiel und ersetzt keine detaillierte Energieauditierung.", styles["Subtle"]))

    doc.build(story)
    return buffer.getvalue()


def make_table(rows):
    table = Table(rows, colWidths=[6.2 * cm, 9.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecfdf5")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def render_header():
    st.markdown(
        """
        <div class="hero">
            <h1>⚡ Energieeffizienz-Check für Fertigungsunternehmen</h1>
            <p>
                Identifizieren Sie Energieeffizienzpotenziale anhand produktionsnaher Daten, Lastgang-Analyse
                und automatisch generierter Kennzahlen. Diese Demo zeigt einen möglichen Ablauf von der Datenerhebung
                bis zum Ergebnisbericht.
            </p>
            <div class="badge-row">
                <span class="badge">Produktionsdaten</span>
                <span class="badge">Energiekennzahlen</span>
                <span class="badge">Lastgang-Analyse</span>
                <span class="badge">PDF-Bericht</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_progress():
    labels = ["Unternehmen", "Produktion", "Energie", "Prozesse", "Lastgang", "Bericht"]
    step = st.session_state.step
    st.progress(step / len(labels))
    st.caption(" → ".join([f"**{label}**" if i + 1 == step else label for i, label in enumerate(labels)]))


def nav_buttons(show_next=True, next_label="Weiter"):
    left, right = st.columns([1, 1])
    with left:
        if st.session_state.step > 1:
            st.button("← Zurück", on_click=previous_step)
    with right:
        if show_next:
            st.button(next_label, on_click=next_step)


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
render_header()
render_progress()

with st.sidebar:
    st.header("Demo-Modus")
    st.write("Diese App ist ein Dummy-Prototyp für eine mögliche Energieeffizienzplattform.")
    st.info("Ohne Upload wird ein synthetischer Lastgang erzeugt, damit die Analyse direkt getestet werden kann.")
    if st.button("Demo zurücksetzen"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


if st.session_state.step == 1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("1. Unternehmenskontext")
    st.write("Bitte geben Sie einige Rahmendaten zum Standort ein.")

    c1, c2 = st.columns(2)
    with c1:
        company_name = st.text_input("Unternehmensname", value=st.session_state.company_data.get("company_name", "Musterfertigung GmbH"))
        industry = st.selectbox(
            "Branche",
            ["Metallverarbeitung", "Kunststoffverarbeitung", "Lebensmittel", "Automotive", "Chemie", "Elektronik", "Sonstige"],
            index=0,
        )
    with c2:
        location = st.text_input("Standort", value=st.session_state.company_data.get("location", "Deutschland"))
        employees = st.number_input("Mitarbeitende am Standort", min_value=1, value=int(st.session_state.company_data.get("employees", 120)))

    st.session_state.company_data = {
        "company_name": company_name,
        "industry": industry,
        "location": location,
        "employees": employees,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


elif st.session_state.step == 2:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("2. Produktionsdaten")
    st.write("Diese Angaben helfen, Energieverbrauch mit Produktionsleistung und Betriebszeiten zu verknüpfen.")

    c1, c2 = st.columns(2)
    with c1:
        shift_model = st.selectbox("Schichtmodell", ["1-Schicht", "2-Schicht", "3-Schicht", "Kontinuierlich / 24-7"], index=1)
        operating_days = st.slider("Produktionstage pro Woche", min_value=1, max_value=7, value=5)
        annual_output = st.number_input("Jährliche Produktionsmenge [Stück/Jahr]", min_value=1, value=100000)
    with c2:
        main_product = st.text_input("Hauptprodukt / Produktgruppe", value="Bauteil A")
        scrap_rate = st.slider("Ausschussquote [%]", min_value=0.0, max_value=25.0, value=3.5, step=0.5)
        bottleneck = st.text_input("Engpassprozess", value="CNC-Bearbeitung")

    st.session_state.production_data = {
        "shift_model": shift_model,
        "operating_days": operating_days,
        "annual_output": annual_output,
        "main_product": main_product,
        "scrap_rate": scrap_rate,
        "bottleneck": bottleneck,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


elif st.session_state.step == 3:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("3. Energiebezogene Daten")
    st.write("Hier werden zentrale Energiedaten erfasst, um Potenziale monetär und energetisch grob zu bewerten.")

    c1, c2 = st.columns(2)
    with c1:
        annual_electricity = st.number_input("Jährlicher Stromverbrauch [kWh/Jahr]", min_value=0, value=850000)
        electricity_price = st.number_input("Strompreis [EUR/kWh]", min_value=0.0, value=0.22, step=0.01)
        peak_price = st.number_input("Leistungspreis [EUR/kW/Jahr]", min_value=0.0, value=120.0, step=5.0)
    with c2:
        has_iso = st.selectbox("Energiemanagement vorhanden?", ["Nein", "ISO 50001", "Energieaudit", "Internes Monitoring"], index=3)
        metering_level = st.selectbox("Messkonzept", ["Nur Hauptzähler", "Linienzähler", "Maschinenzähler", "Energiemonitoring-System"], index=1)
        other_media = st.multiselect("Weitere Medien", ["Druckluft", "Erdgas", "Wärme", "Kälte", "Dampf", "Wasser"], default=["Druckluft"])

    st.session_state.energy_data = {
        "annual_electricity": annual_electricity,
        "electricity_price": electricity_price,
        "peak_price": peak_price,
        "has_iso": has_iso,
        "metering_level": metering_level,
        "other_media": other_media,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


elif st.session_state.step == 4:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("4. Prozesse und vermutete Potenziale")
    st.write("Wählen Sie Prozessbereiche, in denen Sie Einsparpotenziale vermuten.")

    c1, c2 = st.columns(2)
    with c1:
        process_areas = st.multiselect(
            "Relevante Prozessbereiche",
            ["Druckluft", "Absaugung", "Pumpen", "Antriebe", "Kälte", "Wärme", "Beleuchtung", "Standby-Verbrauch", "Gebäudeleittechnik"],
            default=["Druckluft", "Antriebe", "Standby-Verbrauch"],
        )
        maintenance = st.selectbox("Wartungsstrategie", ["Reaktiv", "Regelmäßig", "Zustandsorientiert", "Predictive Maintenance"], index=1)
    with c2:
        known_issues = st.text_area(
            "Bekannte Auffälligkeiten",
            value="Erhöhte Grundlast am Wochenende; einzelne Lastspitzen beim parallelen Anfahren mehrerer Anlagen.",
            height=120,
        )
        goals = st.multiselect(
            "Zielsetzung",
            ["Energiekosten senken", "CO2 reduzieren", "Lastspitzen vermeiden", "Transparenz schaffen", "Audit vorbereiten"],
            default=["Energiekosten senken", "Lastspitzen vermeiden", "Transparenz schaffen"],
        )

    st.session_state.process_data = {
        "process_areas": process_areas,
        "maintenance": maintenance,
        "known_issues": known_issues,
        "goals": goals,
    }
    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons()


elif st.session_state.step == 5:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5. Lastgang hochladen und analysieren")
    st.write("Laden Sie eine CSV- oder Excel-Datei mit Zeitstempel und Leistung hoch. Für die Demo können Sie den Upload überspringen.")

    uploaded = st.file_uploader("Lastgang-Datei hochladen", type=["csv", "xlsx"])

    st.caption("Erwartete Spalten zum Beispiel: `timestamp`, `power_kw`. Andere Spaltennamen werden heuristisch erkannt.")

    if st.button("Analyse starten"):
        try:
            df = read_load_profile(uploaded)
            analysis = analyze_load_profile(df, st.session_state.production_data, st.session_state.energy_data)
            st.session_state.df = df
            st.session_state.analysis = analysis
            st.success("Analyse abgeschlossen. Ergebnisse wurden berechnet.")
        except Exception as exc:
            st.error(f"Die Datei konnte nicht verarbeitet werden: {exc}")

    if st.session_state.analysis is not None:
        analysis = st.session_state.analysis
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Energie", f"{analysis['total_energy']:,.0f} kWh")
        m2.metric("Peak", f"{analysis['peak_power']:,.1f} kW")
        m3.metric("Grundlast", f"{analysis['base_load']:,.1f} kW")
        m4.metric("Zyklen", f"{analysis['detected_cycles']}")

        chart_df = analysis["df"].set_index("timestamp")[["power_kw"]]
        st.line_chart(chart_df)

        st.info("Die Demo erkennt Produktionszyklen über gleitende Mittelwerte und Schwellenwerte. Für echte Projekte sollte diese Logik fachlich angepasst werden.")

    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons(show_next=st.session_state.analysis is not None, next_label="Zum Bericht")


elif st.session_state.step == 6:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("6. Ergebnisbericht erhalten")

    if st.session_state.analysis is None:
        st.warning("Bitte führen Sie zuerst eine Lastgang-Analyse aus.")
        nav_buttons(show_next=False)
    else:
        analysis = st.session_state.analysis

        c1, c2, c3 = st.columns(3)
        c1.metric("Einsparpotenzial", f"{analysis['estimated_savings_kwh']:,.0f} kWh")
        c2.metric("Potenzial monetär", f"{analysis['estimated_savings_eur']:,.0f} EUR")
        c3.metric("Nicht-Produktionsanteil", f"{analysis['non_prod_share'] * 100:.1f} %")

        st.subheader("Priorisierte Hinweise")
        for rec in analysis["recommendations"]:
            st.markdown(f"- {rec}")

        st.divider()
        st.write("Bitte geben Sie eine E-Mail-Adresse ein, um den PDF-Bericht freizuschalten.")
        email = st.text_input("E-Mail-Adresse", value=st.session_state.email, placeholder="name@unternehmen.de")
        st.session_state.email = email

        if is_valid_email(email):
            pdf_bytes = create_pdf_report(
                st.session_state.company_data,
                st.session_state.production_data,
                st.session_state.energy_data,
                st.session_state.process_data,
                analysis,
            )
            st.success("E-Mail-Adresse validiert. Der Demo-Bericht kann heruntergeladen werden.")
            st.download_button(
                "PDF-Bericht herunterladen",
                data=pdf_bytes,
                file_name="energieeffizienz_analyse_demo.pdf",
                mime="application/pdf",
            )
            st.caption("In einer produktiven Version könnte hier zusätzlich ein CRM-, Newsletter- oder E-Mail-Versandprozess angebunden werden.")
        elif email:
            st.error("Bitte geben Sie eine gültige E-Mail-Adresse ein.")
        else:
            st.warning("Der Download wird erst nach Eingabe einer E-Mail-Adresse aktiviert.")

        nav_buttons(show_next=False)

    st.markdown('</div>', unsafe_allow_html=True)
