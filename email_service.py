import smtplib
from email.message import EmailMessage

import streamlit as st


def send_pdf_report_email(recipient_email: str, pdf_bytes: bytes, company_name: str = "") -> None:
    email_config = st.secrets["email"]

    smtp_host = email_config["smtp_host"]
    smtp_port = int(email_config.get("smtp_port", 587))
    smtp_user = email_config["smtp_user"]
    smtp_password = email_config["smtp_password"]
    sender_email = email_config["sender_email"]
    sender_name = email_config.get("sender_name", "Energieeffizienz-Check")

    subject = "Ihr Energieeffizienz-Analysebericht"

    greeting_company = f" für {company_name}" if company_name else ""

    body = f"""
Guten Tag,

vielen Dank für die Nutzung des Energieeffizienz-Checks{greeting_company}.

Im Anhang finden Sie den automatisch generierten PDF-Bericht mit den Ergebnissen der Lastgang- und Energieanalyse.

Hinweis: Dieser Bericht wurde automatisch erstellt und dient als erste Orientierung. Für belastbare Investitions- oder Auditentscheidungen sollte eine detaillierte fachliche Prüfung erfolgen.

Freundliche Grüße
{sender_name}
""".strip()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_email}>"
    message["To"] = recipient_email
    message.set_content(body)

    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename="energieeffizienz_analysebericht.pdf",
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)