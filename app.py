import re

import pandas as pd
import streamlit as st

from analysis import analyze_load_profile, read_load_profile
from report import create_pdf_report


st.set_page_config(
    page_title="Energieeffizienz-Check Produktion",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 1240px;
    }
    .hero {
        background: linear-gradient(135deg, #0f766e 0%, #134e4a 48%, #0f172a 100%);
        padding: 2.2rem 2.4rem;
        border-radius: 30px;
        color: white;
        box-shadow: 0 24px 60px rgba(15, 118, 110, 0.24);
        margin-bottom: 1.6rem;
    }
    .hero h1 {
        font-size: 2.45rem;
        margin-bottom: 0.45rem;
        line-height: 1.08;
    }
    .hero p {
        color: rgba(255, 255, 255, 0.84);
        font-size: 1.05rem;
        max-width: 840px;
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
    .insight {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #0f766e;
        border-radius: 18px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }
    .recommendation-high { border-left: 5px solid #dc2626; }
    .recommendation-medium { border-left: 5px solid #f59e0b; }
    .recommendation-low { border-left: 5px solid #0f766e; }
    .small-muted {
        color: #64748b;
        font-size: 0.92rem;
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


def next_step():
    st.session_state.step = min(st.session_state.step + 1, 6)


def previous_step():
    st.session_state.step = max(st.session_state.step - 1, 1)


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def render_header():
    st.markdown(
        """
        <div class="hero">
            <h1>⚡ Energieeffizienz-Check für Fertigungsunternehmen</h1>
            <p>
                Identifizieren Sie Energieeffizienzpotenziale anhand produktionsnaher Daten,
                Lastgang-Analyse, Zyklenerkennung und automatisch generierter Kennzahlen.
            </p>
            <div class="badge-row">
                <span class="badge">Produktionsdaten</span>
                <span class="badge">Grundlastanalyse</span>
                <span class="badge">Lastspitzen</span>
                <span class="badge">Zyklenerkennung</span>
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


def render_recommendation_card(rec):
    css_class = {
        "hoch": "recommendation-high",
        "mittel": "recommendation-medium",
        "niedrig": "recommendation-low",
    }.get(rec["priority"], "recommendation-low")

    st.markdown(
        f"""
        <div class="insight {css_class}">
            <b>{rec['priority'].upper()} · {rec['title']}</b><br>
            <span class="small-muted">{rec['reason']}</span><br>
            {rec['impact']}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    with st.sidebar:
        st.header("Demo-Modus")
        st.write("Diese App ist ein Dummy-Prototyp für eine mögliche Energieeffizienzplattform.")
        st.info("Ohne Upload wird ein synthetischer Lastgang erzeugt, damit die Analyse direkt getestet werden kann.")
        st.subheader("Nächste Produktidee")
        st.caption("Später könnten Nutzer Projekte speichern, Teams einladen und mehrere Standorte vergleichen.")
        if st.button("Demo zurücksetzen"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def step_company():
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


def step_production():
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


def step_energy():
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


def step_processes():
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


def step_load_profile():
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
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Energie", f"{analysis['total_energy']:,.0f} kWh")
        m2.metric("Peak", f"{analysis['peak_power']:,.1f} kW")
        m3.metric("Grundlast", f"{analysis['base_load']:,.1f} kW")
        m4.metric("Nicht-Produktion", f"{analysis['non_production_share'] * 100:.1f} %")
        m5.metric("Zyklen", f"{analysis['detected_cycles']}")

        tab1, tab2, tab3, tab4 = st.tabs(["Lastgang", "Tagesenergie", "Heatmap", "Lastspitzen"])
        with tab1:
            chart_df = analysis["df"].set_index("timestamp")[["power_kw"]]
            st.line_chart(chart_df)
            st.caption("Die Zyklenerkennung basiert in dieser Demo auf einem gleitenden Mittelwert und einem Quantil-Schwellenwert.")
        with tab2:
            daily = analysis["daily_energy"].copy()
            daily["date"] = pd.to_datetime(daily["date"])
            st.bar_chart(daily.set_index("date")[["energy_kwh"]])
        with tab3:
            st.dataframe(analysis["heatmap_data"].style.format("{:.0f}"), width="stretch")
            st.caption("Durchschnittliche Leistung je Wochentag und Stunde. Hohe Werte außerhalb geplanter Produktion deuten auf Grundlastpotenziale hin.")
        with tab4:
            st.dataframe(analysis["top_peaks"], width="stretch")
            st.caption("Diese Zeitpunkte sind Kandidaten für Lastspitzenmanagement oder detaillierte Ursachenanalyse.")

        st.info("Enthalten: Heatmap, Peak-Liste, Nicht-Produktionsanteil, annualisierte Energie, CO2-Potenzial und priorisierte Empfehlungen.")

    st.markdown('</div>', unsafe_allow_html=True)
    nav_buttons(show_next=st.session_state.analysis is not None, next_label="Zum Bericht")


def step_report():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("6. Ergebnisbericht erhalten")

    if st.session_state.analysis is None:
        st.warning("Bitte führen Sie zuerst eine Lastgang-Analyse aus.")
        nav_buttons(show_next=False)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    analysis = st.session_state.analysis

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Einsparpotenzial", f"{analysis['estimated_savings_kwh']:,.0f} kWh")
    c2.metric("Potenzial monetär", f"{analysis['estimated_savings_eur']:,.0f} EUR")
    c3.metric("CO2-Potenzial", f"{analysis['estimated_co2_savings_t']:.1f} t")
    c4.metric("Peak-Potenzial/Jahr", f"{analysis['peak_savings_eur_year']:,.0f} EUR")

    st.subheader("Priorisierte Handlungsempfehlungen")
    for rec in analysis["recommendations"]:
        render_recommendation_card(rec)

    with st.expander("Technische Kennzahlen anzeigen"):
        kpi_table = pd.DataFrame(
            {
                "Kennzahl": [
                    "Analysierte Tage",
                    "Gesamtenergie [kWh]",
                    "Annualisierte Energie [kWh/Jahr]",
                    "Maximale Leistung [kW]",
                    "Durchschnittsleistung [kW]",
                    "Grundlast [kW]",
                    "Lastfaktor",
                    "Nicht-Produktionsanteil [%]",
                    "Zyklusenergieanteil [%]",
                    "Energie je Einheit [kWh/Stück]",
                ],
                "Wert": [
                    analysis["analyzed_days"],
                    round(analysis["total_energy"], 0),
                    round(analysis["annualized_energy"], 0),
                    round(analysis["peak_power"], 1),
                    round(analysis["avg_power"], 1),
                    round(analysis["base_load"], 1),
                    round(analysis["load_factor"], 2),
                    round(analysis["non_production_share"] * 100, 1),
                    round(analysis["cycle_energy_share"] * 100, 1),
                    round(analysis["energy_per_unit"], 3),
                ],
            }
        )
        st.dataframe(kpi_table, width="stretch")

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
            file_name="energieeffizienz_analyse_demo_v2.pdf",
            mime="application/pdf",
        )
    elif email:
        st.error("Bitte geben Sie eine gültige E-Mail-Adresse ein.")
    else:
        st.warning("Der Download wird erst nach Eingabe einer E-Mail-Adresse aktiviert.")

    nav_buttons(show_next=False)
    st.markdown('</div>', unsafe_allow_html=True)


def main():
    init_state()
    render_header()
    render_progress()
    render_sidebar()

    if st.session_state.step == 1:
        step_company()
    elif st.session_state.step == 2:
        step_production()
    elif st.session_state.step == 3:
        step_energy()
    elif st.session_state.step == 4:
        step_processes()
    elif st.session_state.step == 5:
        step_load_profile()
    elif st.session_state.step == 6:
        step_report()


if __name__ == "__main__":
    main()