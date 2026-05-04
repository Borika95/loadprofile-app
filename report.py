import io
from datetime import datetime

import pandas as pd
from matplotlib import pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image


def fig_to_buffer(fig) -> io.BytesIO:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    buffer.seek(0)
    return buffer


def create_load_plot(df: pd.DataFrame) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10.5, 3.5))
    ax.plot(df["timestamp"], df["power_kw"], linewidth=1.1, label="Leistung")
    ax.scatter(
        df.loc[df["cycle_start"], "timestamp"],
        df.loc[df["cycle_start"], "power_kw"],
        s=12,
        label="Zyklusstart",
    )
    ax.axhline(df["power_kw"].quantile(0.1), linestyle="--", linewidth=1, label="Grundlastniveau")
    ax.set_title("Lastgang mit erkannten Produktionszyklen")
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Leistung [kW]")
    ax.grid(True, alpha=0.28)
    ax.legend(loc="upper right", fontsize=8)
    fig.autofmt_xdate()
    buffer = fig_to_buffer(fig)
    plt.close(fig)
    return buffer


def create_daily_energy_plot(daily_energy: pd.DataFrame) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10.5, 3.2))
    ax.bar(pd.to_datetime(daily_energy["date"]), daily_energy["energy_kwh"])
    ax.set_title("Täglicher Energieverbrauch")
    ax.set_xlabel("Datum")
    ax.set_ylabel("Energie [kWh]")
    ax.grid(True, axis="y", alpha=0.28)
    fig.autofmt_xdate()
    buffer = fig_to_buffer(fig)
    plt.close(fig)
    return buffer


def create_heatmap_plot(heatmap_data: pd.DataFrame) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10.5, 3.5))
    image = ax.imshow(heatmap_data.values, aspect="auto")
    ax.set_title("Lastprofil-Heatmap: Wochentag x Stunde")
    ax.set_xlabel("Stunde")
    ax.set_ylabel("Wochentag")
    ax.set_xticks(range(24))
    ax.set_yticks(range(7))
    ax.set_yticklabels(heatmap_data.index)
    fig.colorbar(image, ax=ax, label="Ø Leistung [kW]")
    buffer = fig_to_buffer(fig)
    plt.close(fig)
    return buffer


def make_table(rows):
    table = Table(rows, colWidths=[6.3 * cm, 9.4 * cm])
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
    styles.add(ParagraphStyle(name="Rec", fontSize=10, leading=13, spaceAfter=7))

    story = []
    story.append(Paragraph("Energieeffizienz-Analyse Produktion", styles["HeroTitle"]))
    story.append(Paragraph(f"Automatisch generierter Demo-Bericht vom {datetime.now().strftime('%d.%m.%Y, %H:%M')} Uhr", styles["Subtle"]))
    story.append(Spacer(1, 0.45 * cm))

    story.append(Paragraph("Executive Summary", styles["Section"]))
    summary = (
        f"Im analysierten Zeitraum von {analysis['analyzed_days']} Tagen wurden "
        f"{analysis['total_energy']:,.0f} kWh Energieverbrauch ausgewertet. "
        f"Die maximale Leistung betrug {analysis['peak_power']:,.1f} kW. "
        f"Das initial geschätzte Einsparpotenzial liegt bei {analysis['estimated_savings_kwh']:,.0f} kWh "
        f"bzw. {analysis['estimated_savings_eur']:,.0f} EUR im Analysezeitraum."
    )
    story.append(Paragraph(summary, styles["BodyText"]))

    company_rows = [
        ["Unternehmen", company_data.get("company_name", "-")],
        ["Branche", company_data.get("industry", "-")],
        ["Standort", company_data.get("location", "-")],
        ["Produktionsmodell", production_data.get("shift_model", "-")],
        ["Messkonzept", energy_data.get("metering_level", "-")],
    ]
    story.append(Paragraph("1. Kontext", styles["Section"]))
    story.append(make_table(company_rows))

    metric_rows = [
        ["Gesamtenergie im Analysezeitraum", f"{analysis['total_energy']:,.0f} kWh"],
        ["Annualisierter Verbrauch", f"{analysis['annualized_energy']:,.0f} kWh/Jahr"],
        ["Maximale Leistung", f"{analysis['peak_power']:,.1f} kW"],
        ["Grundlast", f"{analysis['base_load']:,.1f} kW"],
        ["Lastfaktor", f"{analysis['load_factor']:.2f}"],
        ["Nicht-Produktionsanteil", f"{analysis['non_production_share'] * 100:.1f} %"],
        ["Erkannte Produktionszyklen", f"{analysis['detected_cycles']}"],
        ["Energie je Einheit", f"{analysis['energy_per_unit']:.2f} kWh/Stück"],
        ["Geschätztes Einsparpotenzial", f"{analysis['estimated_savings_kwh']:,.0f} kWh / {analysis['estimated_savings_eur']:,.0f} EUR"],
        ["Geschätzte CO2-Reduktion", f"{analysis['estimated_co2_savings_t']:.1f} t CO2"],
    ]
    story.append(Paragraph("2. Energiekennzahlen", styles["Section"]))
    story.append(make_table(metric_rows))

    story.append(Paragraph("3. Lastgang und Muster", styles["Section"]))
    story.append(Image(create_load_plot(analysis["df"]), width=16 * cm, height=5.2 * cm))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Image(create_daily_energy_plot(analysis["daily_energy"]), width=16 * cm, height=4.8 * cm))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Image(create_heatmap_plot(analysis["heatmap_data"]), width=16 * cm, height=5.1 * cm))

    story.append(Paragraph("4. Priorisierte Handlungsempfehlungen", styles["Section"]))
    for rec in analysis["recommendations"]:
        story.append(
            Paragraph(
                f"<b>{rec['priority'].upper()}: {rec['title']}</b><br/>"
                f"{rec['reason']}<br/><i>{rec['impact']}</i>",
                styles["Rec"],
            )
        )

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Hinweis: Dieser Bericht ist ein Dummy-Beispiel und ersetzt keine detaillierte Energieauditierung.", styles["Subtle"]))

    doc.build(story)
    return buffer.getvalue()