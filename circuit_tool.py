import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd


POWER_PATTERN = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>kw|w|kva|va)(?=$|\s|[;|,)])", re.IGNORECASE)
CURRENT_PATTERN = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>a)\b", re.IGNORECASE)
VOLTAGE_PATTERN = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>v)\b", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"(?:^|\s)(?P<tag>[=+\-]?[A-Z]{1,4}\d{1,5}(?:[./_-]\d{1,4})?)(?:\s|$)")
PREFERRED_IDENTIFIER_PATTERNS = [
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}M\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}E\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}K\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}Q\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
]

CONSUMER_KEYWORDS = {
    "Motor": ["motor", "antrieb", "drive", "servo", "spindel"],
    "Pumpe": ["pumpe", "pump", "förderpumpe", "waschpumpe"],
    "Ventilator": ["lüfter", "ventilator", "fan", "gebläse", "exhaust"],
    "Heizung": ["heizung", "heiz", "heater", "heating", "trocknung", "drying"],
    "Kompressor": ["kompressor", "compressor", "verdichter"],
    "Kälte": ["kälte", "cooling", "chiller", "kühler"],
    "Absaugung": ["absaugung", "extraction", "suction"],
    "Transformator": ["trafo", "transformator", "transformer"],
}

EXCLUSION_KEYWORDS = [
    "inhaltsverzeichnis",
    "vorsicherung",
    "kabeltyp",
    "silikonleitung",
    "leitung",
    "mm²",
    "mm2",
    "pnoz",
    "mico",
    "pro eco",
    "sicherheitsschaltgerät",
    "3x 400v/n/pe",
    "x0pe",
    "xpe",
    "pepe",
    "siemens",
    "schütz",
    "leuchtmelder",
    "leuchtdrucktaster",
    "zugfeder",
]

PORTFOLIO_RECOMMENDATIONS = {
    "I": "Kontinuierliche Messung priorisieren: hoher Nutzungsgrad und lange Nutzungszeit.",
    "II": "Zeitlich fokussiert messen: hoher Nutzungsgrad, aber begrenzte Laufzeit.",
    "III": "Monitoring prüfen: lange Laufzeit, aber niedriger Nutzungsgrad.",
    "IV": "Keine permanente Messung priorisieren; bei Bedarf Stichproben oder Sammelmessung.",
}


def _to_float(value: str | int | float | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _power_to_kw(value: str, unit: str) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    unit_normalized = unit.lower()
    if unit_normalized == "w":
        return number / 1000
    if unit_normalized == "va":
        return number / 1000
    return number


def _first_number(pattern: re.Pattern, text: str) -> float | None:
    match = pattern.search(text)
    if not match:
        return None
    return _to_float(match.group("value"))


def _extract_text_with_pypdf(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return ""
    return "\n\f\n".join(page_text)


def _can_write_working_directory() -> bool:
    probe_path = Path.cwd() / ".circuit_tool_write_probe"
    try:
        probe_path.write_bytes(b"")
        probe_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _extract_text_with_pdftotext(pdf_bytes: bytes) -> str:
    executable = shutil.which("pdftotext")
    if not executable or not _can_write_working_directory():
        return ""

    try:
        with tempfile.TemporaryDirectory(dir=Path.cwd(), ignore_cleanup_errors=True) as temp_dir:
            pdf_path = Path(temp_dir) / "input.pdf"
            pdf_path.write_bytes(pdf_bytes)
            result = subprocess.run(
                [executable, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
                capture_output=True,
                timeout=45,
                check=False,
            )
            return result.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, str]:
    pypdf_text = _extract_text_with_pypdf(pdf_bytes)
    if len(pypdf_text.strip()) > 80:
        return pypdf_text, "pypdf"

    pdftotext_text = _extract_text_with_pdftotext(pdf_bytes)
    if len(pdftotext_text.strip()) > 80:
        return pdftotext_text, "pdftotext"

    return "", "none"


def detect_consumer_type(text: str) -> str:
    text_lower = text.lower()
    if re.search(r"(?<![A-Z0-9])-\d{0,3}M\d{1,4}\b", text, re.IGNORECASE):
        return "Motor"
    if re.search(r"(?<![A-Z0-9])-\d{0,3}E\d{1,4}\b", text, re.IGNORECASE):
        return "Heizung"
    for consumer_type, keywords in CONSUMER_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            return consumer_type
    return "Unklar"


def extract_identifier(text: str) -> str:
    for pattern in PREFERRED_IDENTIFIER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group("tag").strip()
    match = IDENTIFIER_PATTERN.search(text)
    return match.group("tag").strip() if match else ""


def extract_power_kw(text: str) -> float | None:
    match = POWER_PATTERN.search(text)
    if not match:
        return None
    return _power_to_kw(match.group("value"), match.group("unit"))


def clean_designation(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    collapsed = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:kw|w|kva|va|a|v)\b", "", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\s{2,}", " ", collapsed).strip(" -;|")
    return collapsed[:110] if collapsed else "Unbenannter Verbraucher"


def extract_consumers_locally(pdf_text: str) -> list[dict[str, Any]]:
    pages = re.split(r"\f+", pdf_text)
    consumers = []
    seen_keys = set()

    for page_index, page_text in enumerate(pages, start=1):
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for line_index, line in enumerate(lines):
            line_type = detect_consumer_type(line)
            has_power = bool(POWER_PATTERN.search(line))
            if line_type == "Unklar" and not has_power:
                continue

            window_start = max(0, line_index - 2)
            window_end = min(len(lines), line_index + 3)
            snippet = " | ".join(lines[window_start:window_end])

            consumer_type = detect_consumer_type(snippet)
            power_kw = extract_power_kw(snippet)
            if consumer_type == "Unklar" and power_kw is None:
                continue
            if consumer_type == "Unklar" and any(keyword in snippet.lower() for keyword in EXCLUSION_KEYWORDS):
                continue

            identifier = extract_identifier(snippet)
            designation = clean_designation(line if consumer_type != "Unklar" else snippet)
            current_a = _first_number(CURRENT_PATTERN, snippet)
            voltage_v = _first_number(VOLTAGE_PATTERN, snippet)

            dedupe_key = (page_index, identifier.lower(), round(power_kw or 0, 3)) if identifier else (
                page_index,
                designation.lower(),
                round(power_kw or 0, 3),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            confidence = 0.42
            if consumer_type != "Unklar":
                confidence += 0.22
            if power_kw is not None:
                confidence += 0.2
            if identifier:
                confidence += 0.08
            if current_a is not None or voltage_v is not None:
                confidence += 0.05
            if power_kw is None:
                confidence = min(confidence, 0.5)

            consumers.append(
                {
                    "detection_id": len(consumers) + 1,
                    "page": page_index,
                    "identifier": identifier,
                    "designation": designation,
                    "consumer_type": consumer_type,
                    "nominal_power_kw": power_kw,
                    "nominal_current_a": current_a,
                    "voltage_v": voltage_v,
                    "cabinet": "",
                    "source": "Lokale Textanalyse",
                    "confidence": min(confidence, 0.95),
                    "source_snippet": snippet[:500],
                }
            )

    return consumers


def _get_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def extract_consumers_with_openai(
    pdf_text: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    max_chars: int = 60000,
) -> list[dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Das Python-Paket 'openai' ist nicht installiert.") from exc

    client = OpenAI(api_key=api_key)
    prompt = f"""
Extrahiere elektrische Verbraucher aus dem Text eines PDF-Schaltplans.
Nutze technisches Kontextwissen, aber erfinde keine Werte.
Gib ausschließlich JSON zurück mit dem Schlüssel "consumers".
Jeder Verbraucher soll diese Felder haben:
detection_id, page, identifier, designation, consumer_type, nominal_power_kw,
nominal_current_a, voltage_v, cabinet, confidence, source_snippet.

Hinweise:
- nominal_power_kw ist eine Zahl in kW oder null.
- consumer_type ist z. B. Motor, Pumpe, Ventilator, Heizung, Kompressor, Kälte, Absaugung, Transformator oder Unklar.
- confidence liegt zwischen 0 und 1.
- source_snippet ist ein kurzer Auszug, der die Extraktion begründet.

PDF-Text:
{pdf_text[:max_chars]}
""".strip()

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Du bist ein Assistent für die Analyse industrieller elektrischer Schaltpläne.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = _get_json_object(content)
    return normalize_consumers(payload.get("consumers", []), source="KI-Assistenz")


def render_pdf_pages_to_images(pdf_bytes: bytes, max_pages: int = 6, dpi: int = 150) -> list[bytes]:
    executable = shutil.which("pdftoppm")
    if not executable or not _can_write_working_directory():
        return []

    try:
        with tempfile.TemporaryDirectory(dir=Path.cwd(), ignore_cleanup_errors=True) as temp_dir:
            pdf_path = Path(temp_dir) / "input.pdf"
            output_prefix = Path(temp_dir) / "page"
            pdf_path.write_bytes(pdf_bytes)

            result = subprocess.run(
                [
                    executable,
                    "-png",
                    "-r",
                    str(dpi),
                    "-f",
                    "1",
                    "-l",
                    str(max_pages),
                    str(pdf_path),
                    str(output_prefix),
                ],
                capture_output=True,
                timeout=90,
                check=False,
            )
            if result.returncode != 0 and not list(Path(temp_dir).glob("page-*.png")):
                return []
            return [path.read_bytes() for path in sorted(Path(temp_dir).glob("page-*.png"))]
    except Exception:
        return []


def extract_consumers_with_openai_vision(
    pdf_bytes: bytes,
    api_key: str,
    model: str = "gpt-4o-mini",
    max_pages: int = 6,
) -> list[dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Das Python-Paket 'openai' ist nicht installiert.") from exc

    page_images = render_pdf_pages_to_images(pdf_bytes, max_pages=max_pages)
    if not page_images:
        raise RuntimeError("PDF-Seiten konnten nicht als Bilder gerendert werden.")

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": """
Analysiere die folgenden Seiten eines elektrischen Schaltplans.
Extrahiere elektrische Verbraucher und technische Metadaten.
Gib ausschließlich JSON zurück mit dem Schlüssel "consumers".
Jeder Verbraucher soll diese Felder haben:
detection_id, page, identifier, designation, consumer_type, nominal_power_kw,
nominal_current_a, voltage_v, cabinet, confidence, source_snippet.
Erfinde keine Werte. Nutze null, wenn ein Wert nicht lesbar ist.
""".strip(),
        }
    ]

    for page_index, image_bytes in enumerate(page_images, start=1):
        encoded = base64.b64encode(image_bytes).decode("ascii")
        content.append({"type": "text", "text": f"Seite {page_index}"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            }
        )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Du bist ein Assistent für die Analyse industrieller elektrischer Schaltpläne.",
            },
            {"role": "user", "content": content},
        ],
    )
    payload = _get_json_object(response.choices[0].message.content or "{}")
    return normalize_consumers(payload.get("consumers", []), source="KI-Vision")


def normalize_consumers(consumers: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    normalized = []
    for index, item in enumerate(consumers, start=1):
        power_kw = _to_float(item.get("nominal_power_kw"))
        current_a = _to_float(item.get("nominal_current_a"))
        voltage_v = _to_float(item.get("voltage_v"))
        confidence = _to_float(item.get("confidence"))
        normalized.append(
            {
                "detection_id": int(item.get("detection_id") or index),
                "page": int(item.get("page") or 0),
                "identifier": str(item.get("identifier") or "").strip(),
                "designation": str(item.get("designation") or "Unbenannter Verbraucher").strip(),
                "consumer_type": str(item.get("consumer_type") or "Unklar").strip(),
                "nominal_power_kw": power_kw,
                "nominal_current_a": current_a,
                "voltage_v": voltage_v,
                "cabinet": str(item.get("cabinet") or "").strip(),
                "source": source,
            "confidence": min(max(confidence if confidence is not None else 0.55, 0), 1),
            "source_snippet": str(item.get("source_snippet") or "").strip()[:500],
            "utilization_pct": _to_float(item.get("utilization_pct")),
            "operating_time_pct": _to_float(item.get("operating_time_pct")),
        }
        )
    return normalized


def analyze_circuit_pdf(
    pdf_bytes: bytes,
    file_name: str,
    use_ai: bool = False,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    pdf_text, extraction_engine = extract_pdf_text(pdf_bytes)
    messages = []

    if not pdf_text.strip():
        if use_ai and api_key:
            try:
                consumers = extract_consumers_with_openai_vision(
                    pdf_bytes,
                    api_key,
                    model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                )
                return {
                    "file_name": file_name,
                    "pages_analyzed": 0,
                    "text_characters": 0,
                    "text_engine": "vision",
                    "recognition_engine": "KI-Vision",
                    "messages": [
                        "Aus dem PDF konnte kein Text extrahiert werden. Die KI-Vision hat gerenderte Seitenbilder analysiert."
                    ],
                    "consumers": consumers,
                }
            except Exception as exc:
                messages.append(f"KI-Vision nicht verfügbar: {exc}")
        return {
            "file_name": file_name,
            "pages_analyzed": 0,
            "text_characters": 0,
            "text_engine": extraction_engine,
            "recognition_engine": "Keine Erkennung",
            "messages": messages
            + ["Aus dem PDF konnte kein Text extrahiert werden. Für gescannte Schaltpläne ist ein KI-Vision-Backend nötig."],
            "consumers": [],
        }

    if use_ai and api_key:
        try:
            consumers = extract_consumers_with_openai(pdf_text, api_key, model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
            recognition_engine = "KI-Assistenz"
        except Exception as exc:
            messages.append(f"KI-Erkennung nicht verfügbar, lokale Textanalyse verwendet: {exc}")
            consumers = normalize_consumers(extract_consumers_locally(pdf_text), source="Lokale Textanalyse")
            recognition_engine = "Lokale Textanalyse"
    else:
        if use_ai and not api_key:
            messages.append("Kein OpenAI API-Key gefunden, lokale Textanalyse verwendet.")
        consumers = normalize_consumers(extract_consumers_locally(pdf_text), source="Lokale Textanalyse")
        recognition_engine = "Lokale Textanalyse"

    return {
        "file_name": file_name,
        "pages_analyzed": max(len(re.split(r"\f+", pdf_text)), 1),
        "text_characters": len(pdf_text),
        "text_engine": extraction_engine,
        "recognition_engine": recognition_engine,
        "messages": messages,
        "consumers": consumers,
    }


def demo_circuit_result() -> dict[str, Any]:
    consumers = [
        {
            "detection_id": 1,
            "page": 24,
            "identifier": "-M11",
            "designation": "Hot-air drying",
            "consumer_type": "Heizung",
            "nominal_power_kw": 11.0,
            "nominal_current_a": None,
            "voltage_v": 400.0,
            "cabinet": "+S1",
            "source": "Demo",
            "confidence": 0.98,
            "source_snippet": "Hot-air drying 11 kW",
            "utilization_pct": 80,
            "operating_time_pct": 20,
        },
        {
            "detection_id": 2,
            "page": 31,
            "identifier": "-M21",
            "designation": "Washing pump",
            "consumer_type": "Pumpe",
            "nominal_power_kw": 3.0,
            "nominal_current_a": None,
            "voltage_v": 400.0,
            "cabinet": "+S1",
            "source": "Demo",
            "confidence": 0.96,
            "source_snippet": "Washing pump 3 kW",
            "utilization_pct": 80,
            "operating_time_pct": 50,
        },
        {
            "detection_id": 3,
            "page": 38,
            "identifier": "-M31",
            "designation": "Exhaust fan",
            "consumer_type": "Ventilator",
            "nominal_power_kw": 0.25,
            "nominal_current_a": None,
            "voltage_v": 230.0,
            "cabinet": "+S2",
            "source": "Demo",
            "confidence": 0.94,
            "source_snippet": "Exhaust fan 0.25 kW",
            "utilization_pct": 20,
            "operating_time_pct": 20,
        },
        {
            "detection_id": 4,
            "page": 42,
            "identifier": "-M41",
            "designation": "Rotational drive",
            "consumer_type": "Motor",
            "nominal_power_kw": 0.18,
            "nominal_current_a": None,
            "voltage_v": 230.0,
            "cabinet": "+S2",
            "source": "Demo",
            "confidence": 0.94,
            "source_snippet": "Rotational drive 0.18 kW",
            "utilization_pct": 25,
            "operating_time_pct": 55,
        },
        {
            "detection_id": 5,
            "page": 46,
            "identifier": "-M51",
            "designation": "Oil skimmer",
            "consumer_type": "Motor",
            "nominal_power_kw": 0.09,
            "nominal_current_a": None,
            "voltage_v": 230.0,
            "cabinet": "+S2",
            "source": "Demo",
            "confidence": 0.91,
            "source_snippet": "Oil skimmer 0.09 kW",
            "utilization_pct": 15,
            "operating_time_pct": 18,
        },
        {
            "detection_id": 6,
            "page": 52,
            "identifier": "-M61",
            "designation": "Unspecified auxiliary motor",
            "consumer_type": "Motor",
            "nominal_power_kw": None,
            "nominal_current_a": None,
            "voltage_v": 400.0,
            "cabinet": "+S3",
            "source": "Demo",
            "confidence": 0.72,
            "source_snippet": "Auxiliary motor without nominal power",
            "utilization_pct": 35,
            "operating_time_pct": 15,
        },
    ]
    return {
        "file_name": "Demo: BvL OceanRC 750",
        "pages_analyzed": 72,
        "text_characters": 0,
        "text_engine": "Demo",
        "recognition_engine": "Demo",
        "messages": [],
        "consumers": consumers,
    }


def consumers_to_dataframe(consumers: list[dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "detection_id",
        "page",
        "identifier",
        "designation",
        "consumer_type",
        "nominal_power_kw",
        "nominal_current_a",
        "voltage_v",
        "cabinet",
        "source",
        "confidence",
        "source_snippet",
        "utilization_pct",
        "operating_time_pct",
    ]
    return pd.DataFrame(consumers, columns=columns)


def build_abc_analysis(consumers_df: pd.DataFrame, a_limit: float = 80.0, b_limit: float = 90.0) -> pd.DataFrame:
    if consumers_df.empty or "nominal_power_kw" not in consumers_df:
        return pd.DataFrame()

    df = consumers_df.copy()
    df["nominal_power_kw"] = pd.to_numeric(df["nominal_power_kw"], errors="coerce")
    df = df.dropna(subset=["nominal_power_kw"])
    df = df[df["nominal_power_kw"] > 0].sort_values("nominal_power_kw", ascending=False)
    if df.empty:
        return df

    total_power = df["nominal_power_kw"].sum()
    total_consumers = len(df)
    df["share_power_pct"] = df["nominal_power_kw"] / total_power * 100
    df["cum_power_pct"] = df["share_power_pct"].cumsum()
    df["share_consumers_pct"] = 100 / total_consumers
    df["cum_consumers_pct"] = df["share_consumers_pct"].cumsum()
    previous_cum_power = df["cum_power_pct"].shift(fill_value=0)
    df["abc_group"] = [
        "A" if cumulative <= a_limit or index == 0 else "B" if previous < b_limit else "C"
        for index, (cumulative, previous) in enumerate(zip(df["cum_power_pct"], previous_cum_power))
    ]
    return df


def prepare_portfolio_input(consumers_df: pd.DataFrame) -> pd.DataFrame:
    if consumers_df.empty:
        return consumers_df

    df = consumers_df.copy()
    df["nominal_power_kw"] = pd.to_numeric(df["nominal_power_kw"], errors="coerce")
    df["utilization_pct"] = df.get("utilization_pct", 50)
    df["operating_time_pct"] = df.get("operating_time_pct", 40)

    for column in ["utilization_pct", "operating_time_pct"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(50).clip(0, 100)
    return df


def classify_portfolio(
    consumers_df: pd.DataFrame,
    utilization_threshold: float = 50.0,
    time_threshold: float = 50.0,
) -> pd.DataFrame:
    if consumers_df.empty:
        return consumers_df

    df = prepare_portfolio_input(consumers_df)

    def classify(row: pd.Series) -> str:
        high_utilization = row["utilization_pct"] >= utilization_threshold
        high_time = row["operating_time_pct"] >= time_threshold
        if high_utilization and high_time:
            return "I"
        if high_utilization and not high_time:
            return "II"
        if not high_utilization and high_time:
            return "III"
        return "IV"

    df["portfolio_class"] = df.apply(classify, axis=1)
    df["metering_recommendation"] = df["portfolio_class"].map(PORTFOLIO_RECOMMENDATIONS)
    return df
