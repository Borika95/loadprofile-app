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


LOCAL_EXTRACTION_VERSION = "text-layout-v3"
POWER_PATTERN = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>kw|w|kva|va)(?=$|\s|[;|,)])", re.IGNORECASE)
CURRENT_PATTERN = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>a)\b", re.IGNORECASE)
VOLTAGE_PATTERN = re.compile(r"(?P<value>\d+(?:[,.]\d+)?)\s*(?P<unit>v)\b", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"(?:^|\s)(?P<tag>[=+\-]?[A-Z]{1,4}\d{1,5}(?:[./_-]\d{1,4})?)(?:\s|$)")
PREFERRED_IDENTIFIER_PATTERNS = [
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}M\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}E\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}K\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>-\d{0,3}Q\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9/])(?P<tag>\d{1,3}M\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9/])(?P<tag>\d{1,3}E\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9/])(?P<tag>\d{1,3}K\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])(?P<tag>[A-Z]\d{1,2}-\d{2}[MEK]\d{1,4}(?:[./_-]\d{1,4})?)\b", re.IGNORECASE),
]
LOCAL_IDENTIFIER_PATTERNS = [
    PREFERRED_IDENTIFIER_PATTERNS[0],
    PREFERRED_IDENTIFIER_PATTERNS[1],
    PREFERRED_IDENTIFIER_PATTERNS[2],
    PREFERRED_IDENTIFIER_PATTERNS[4],
    PREFERRED_IDENTIFIER_PATTERNS[5],
    PREFERRED_IDENTIFIER_PATTERNS[6],
    PREFERRED_IDENTIFIER_PATTERNS[7],
]

CONSUMER_KEYWORDS = {
    "Motor": [
        "motor",
        "antrieb",
        "drive",
        "servo",
        "spindel",
        "stellklappe",
        "rotationsantrieb",
        "ölskimmer",
        "oelskimmer",
        "skimmer",
    ],
    "Pumpe": [
        "pumpe",
        "pump",
        "förderpumpe",
        "foerderpumpe",
        "waschpumpe",
        "ölpumpe",
        "oelpumpe",
        "hochdruckpumpe",
        "ölhochdruckpumpe",
        "oelhochdruckpumpe",
        "hydraulikpumpe",
        "kühlmittelpumpe",
        "kuehlmittelpumpe",
    ],
    "Ventilator": [
        "lüfter",
        "luefter",
        "ventilator",
        "absaugventilator",
        "kabinenlüfter",
        "kabinenluefter",
        "fan",
        "gebläse",
        "geblaese",
        "exhaust",
    ],
    "Heizung": ["heizung", "heiz", "heater", "heating", "trocknung", "drying"],
    "Kompressor": ["kompressor", "compressor", "verdichter"],
    "Kälte": [
        "kälte",
        "kaelte",
        "kühl",
        "kuehl",
        "kühler",
        "kuehler",
        "kühlgerät",
        "kuehlgeraet",
        "kühlmittel",
        "kuehlmittel",
        "oelkühler",
        "oelkuehler",
        "cooling",
        "chiller",
    ],
    "Absaugung": ["absaugung", "extraction", "suction"],
    "Transformator": ["trafo", "transformator", "transformer"],
}
CONSUMER_TYPE_PRIORITY = ["Pumpe", "Ventilator", "Kälte", "Heizung", "Kompressor", "Absaugung", "Transformator", "Motor"]

EXCLUSION_KEYWORDS = [
    "inhaltsverzeichnis",
    "vorsicherung",
    "gesamtanschlusswert",
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
    "motorschutzschalter",
    "leistungsschalter",
    "sicherungsautomat",
    "zugfeder",
]

PAGE_EXCLUSION_MARKERS = [
    "inhaltsverzeichnis",
    "klemmenplan",
    "kennzeichnung",
    "anordnungsplan",
    "geraeteanordnung",
    "geräteanordnung",
    "artikelstueckliste",
    "artikelstückliste",
    "artikelsummenstueckliste",
    "artikelsummenstückliste",
    "stueckliste",
    "stückliste",
    "legende",
    "farbkennzeichnung",
    "strukturkennzeichen",
    "betriebsmittelkennzeichnung",
    "seitenbezogene bereichs-einteilung",
    "codierplan",
    "strombelastbarkeit",
    "leiterfarben",
    "drehmomententabelle",
    "vorschriften schaltschrank",
    "vorschriften maschine",
    "schaltschrankaufbau",
    "montageplattenaufbau",
]

LINE_NOISE_MARKERS = [
    "änderung",
    "bearb.",
    "gepr.",
    "datum",
    "ersatz",
    "ursprung",
    "norm en",
    "blatt",
    "alle leitungen",
    "technische unterlagen",
    "anschlussplan",
    "ohne bediengeräteschrank",
    "kommission",
    "projekt",
    "bvl oberflächentechnik",
    "pfronten gmbh",
    "revision",
    "ausschaltverzögert",
    "ausschaltverzoegert",
    "prozessüberwachung",
    "prozessueberwachung",
    "werkzeugüberwachung",
    "werkzeugueberwachung",
    "not-halt",
    "haltverzögert",
    "haltverzoegert",
    "überbrück",
    "ueberbrueck",
    "muting",
    "störung",
    "stoerung",
    "freigabe",
    "sammelstörung",
    "sammelstoerung",
    "akkumulator",
    "accumulator",
    "t=45s",
]

FOOTER_LINE_MARKERS = [
    "änderung",
    "bearb.",
    "gepr.",
    "datum",
    "ersatz",
    "ursprung",
    "norm en",
    "kommission",
    "projektnummer",
    "bvl oberflächentechnik",
    "pfronten gmbh",
    "deckel maho",
    "revision",
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


def _normalize_search_text(text: str) -> str:
    return text.casefold().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))


def _contains_keyword(text: str, keywords: list[str]) -> bool:
    normalized = _normalize_search_text(text)
    return any(_normalize_search_text(keyword) in normalized for keyword in keywords)


def _contains_exclusion(text: str) -> bool:
    normalized = _normalize_search_text(text)
    return any(_normalize_search_text(keyword) in normalized for keyword in EXCLUSION_KEYWORDS)


def _identifier_family(identifier: str) -> str:
    match = re.search(r"([MEKQ])\d{1,4}(?:[./_-]\d{1,4})?$", identifier.upper())
    return match.group(1) if match else ""


def _page_should_be_skipped(page_text: str) -> bool:
    normalized = _normalize_search_text(page_text)
    if not normalized.strip():
        return True

    always_skip = [
        "inhaltsverzeichnis",
        "klemmenplan",
        "anordnungsplan",
        "geraeteanordnung",
        "artikelstueckliste",
        "artikelsummenstueckliste",
        "stueckliste",
        "seitenbezogene bereichs-einteilung",
    ]
    if any(marker in normalized for marker in always_skip):
        return True

    if len(re.findall(r"\b\d+\s*/\s*stromlaufplan\b", normalized)) >= 3:
        return True
    if "seite" in normalized and "seitenbeschreibung" in normalized:
        return True
    if "bmk" in normalized and "benennung" in normalized and "blatt" in normalized:
        return True

    if "stromlaufplan" in normalized:
        return False

    return any(_normalize_search_text(marker) in normalized for marker in PAGE_EXCLUSION_MARKERS)


def _iter_local_identifier_matches(line: str):
    seen_spans = set()
    for pattern in LOCAL_IDENTIFIER_PATTERNS:
        for match in pattern.finditer(line):
            span = match.span("tag")
            if span in seen_spans:
                continue
            seen_spans.add(span)
            yield match


def _line_window(lines: list[str], line_index: int, before: int = 4, after: int = 9) -> list[str]:
    return lines[max(0, line_index - before) : min(len(lines), line_index + after + 1)]


def _column_window(lines: list[str], line_index: int, match: re.Match, before: int = 6, after: int = 12) -> list[str]:
    start, end = match.span("tag")
    center = (start + end) // 2
    left = max(0, center - 28)
    right = center + 46
    return [line[left:right] for line in _line_window(lines, line_index, before=before, after=after)]


def _is_cable_reference_match(line: str, match: re.Match) -> bool:
    start, end = match.span("tag")
    nearby = line[max(0, start - 8) : min(len(line), end + 8)].upper()
    return "/" in line[max(0, start - 3) : start] or "W-X" in nearby


def _component_anchor_matches(lines: list[str]) -> list[tuple[int, re.Match]]:
    anchors: list[tuple[int, re.Match]] = []
    for line_index, line in enumerate(lines):
        for match in _iter_local_identifier_matches(line):
            family = _identifier_family(match.group("tag"))
            if family not in {"M", "E"}:
                continue
            if _is_cable_reference_match(line, match):
                continue
            anchors.append((line_index, match))
    return anchors


def _column_bounds_for_anchor(anchor_index: int, anchors: list[tuple[int, re.Match]], max_width: int) -> tuple[int, int]:
    centers = sorted((match.span("tag")[0] + match.span("tag")[1]) // 2 for _, match in anchors)
    _, match = anchors[anchor_index]
    center = (match.span("tag")[0] + match.span("tag")[1]) // 2
    previous_centers = [candidate for candidate in centers if candidate < center]
    next_centers = [candidate for candidate in centers if candidate > center]

    left = max(0, int((previous_centers[-1] + center) / 2) if previous_centers else center - 42)
    right = min(max_width, int((center + next_centers[0]) / 2) if next_centers else center + 56)
    return left, min(max_width, right + 8)


def _clean_column_label(text: str) -> str:
    designation = clean_designation(text)
    if designation == "Unbenannter Verbraucher":
        return ""
    if ";" in designation:
        return ""
    normalized = _normalize_search_text(designation)
    if any(marker in normalized for marker in LINE_NOISE_MARKERS):
        return ""
    if normalized in {"m", "reserve", "no com", "sockel"}:
        return ""
    if re.search(r"\b(?:u1|v1|w1|pe|g?nye|bn|bk|gy|l1|l2|l3|mm2|mm²)\b", normalized):
        return ""
    if POWER_PATTERN.search(text) or CURRENT_PATTERN.search(text) or VOLTAGE_PATTERN.search(text):
        return ""
    if any(pattern.search(text) for pattern in PREFERRED_IDENTIFIER_PATTERNS):
        return ""
    if len(re.sub(r"[^A-Za-zÄÖÜäöüß]", "", designation)) < 4:
        return ""
    return designation


def _best_column_designation(column_lines: list[str], identifier_line_offset: int) -> str:
    labels: list[tuple[int, str]] = []
    for offset, line in enumerate(column_lines[identifier_line_offset + 1 :], start=identifier_line_offset + 1):
        label = _clean_column_label(line)
        if not label:
            continue
        labels.append((offset, label))

    if not labels:
        return ""

    typed_labels = [(offset, label) for offset, label in labels if detect_consumer_type(label) != "Unklar"]
    selected_offset, selected_label = typed_labels[0] if typed_labels else labels[0]
    combined = [selected_label]
    for offset, label in labels:
        if offset <= selected_offset:
            continue
        if offset - selected_offset > 3:
            break
        if label not in combined and len(" ".join(combined + [label])) <= 95:
            combined.append(label)

    return " ".join(combined)


def _extract_column_aligned_consumers(lines: list[str], page_index: int) -> list[dict[str, Any]]:
    anchors = _component_anchor_matches(lines)
    if not anchors:
        return []

    max_width = max(len(line) for line in lines)
    consumers: list[dict[str, Any]] = []
    for anchor_index, (line_index, match) in enumerate(anchors):
        identifier = _normalize_identifier_tag(match.group("tag").strip())
        family = _identifier_family(identifier)
        left, right = _column_bounds_for_anchor(anchor_index, anchors, max_width)
        window_start = max(0, line_index - 5)
        footer_start = len(lines)
        for candidate_index in range(line_index + 1, len(lines)):
            normalized_line = _normalize_search_text(lines[candidate_index])
            if any(_normalize_search_text(marker) in normalized_line for marker in FOOTER_LINE_MARKERS):
                footer_start = candidate_index
                break
        window_end = min(footer_start, line_index + 12)
        column_lines = [line[left:right] for line in lines[window_start:window_end]]
        identifier_line_offset = line_index - window_start
        context = " | ".join(part.strip() for part in column_lines if part.strip())

        designation = _best_column_designation(column_lines, identifier_line_offset)
        if not designation:
            continue

        consumer_type = detect_consumer_type(designation)
        if consumer_type == "Unklar":
            consumer_type = detect_consumer_type(context)
        if family == "E" and consumer_type == "Unklar":
            consumer_type = "Heizung"
        if consumer_type == "Unklar":
            continue

        power_kw = extract_power_kw(context)
        current_a = _first_number(CURRENT_PATTERN, context)
        voltage_v = _first_number(VOLTAGE_PATTERN, context)
        confidence = 0.62
        if power_kw is not None:
            confidence += 0.16
        if current_a is not None or voltage_v is not None:
            confidence += 0.05
        if detect_consumer_type(designation) != "Unklar":
            confidence += 0.14
        if family in {"M", "E"}:
            confidence += 0.04

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
                "confidence": min(confidence, 0.98),
                "source_snippet": context[:500],
            }
        )

    return consumers


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
    pdftotext_text = _extract_text_with_pdftotext(pdf_bytes)
    if len(pdftotext_text.strip()) > 80:
        return pdftotext_text, "pdftotext"

    pypdf_text = _extract_text_with_pypdf(pdf_bytes)
    if len(pypdf_text.strip()) > 80:
        return pypdf_text, "pypdf"

    return "", "none"


def detect_consumer_type(text: str) -> str:
    for consumer_type in CONSUMER_TYPE_PRIORITY:
        if _contains_keyword(text, CONSUMER_KEYWORDS[consumer_type]):
            return consumer_type
    if re.search(r"(?<![A-Z0-9])-\d{0,3}M\d{1,4}\b", text, re.IGNORECASE):
        return "Motor"
    if re.search(r"(?<![A-Z0-9])-\d{0,3}E\d{1,4}\b", text, re.IGNORECASE):
        return "Heizung"
    return "Unklar"


def extract_identifier(text: str) -> str:
    for pattern in PREFERRED_IDENTIFIER_PATTERNS:
        match = pattern.search(text)
        if match:
            return _normalize_identifier_tag(match.group("tag").strip())
    match = IDENTIFIER_PATTERN.search(text)
    return _normalize_identifier_tag(match.group("tag").strip()) if match else ""


def _normalize_identifier_tag(tag: str) -> str:
    if re.match(r"^\d{1,3}[MEK]\d{1,4}(?:[./_-]\d{1,4})?$", tag, re.IGNORECASE):
        return f"-{tag}"
    return tag


def extract_power_kw(text: str) -> float | None:
    match = POWER_PATTERN.search(text)
    if not match:
        return None
    return _power_to_kw(match.group("value"), match.group("unit"))


def clean_designation(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    collapsed = re.sub(r"\bN/C\b", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\+\w+", " ", collapsed)
    collapsed = re.sub(r"\bBSTA\s*\d+[A-Z0-9./_-]*", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\bDECKEL\s+MAHO\b", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\bDMU\s*\d+\b", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\bBvL\s+Oberflächentechnik\b", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\b\d+\s*Bl\.", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"^\s*DE\s+", " ", collapsed)
    collapsed = re.sub(r"^\s*M\s+", " ", collapsed)
    collapsed = re.sub(r"^\s*/[A-Z]\s+", " ", collapsed)
    collapsed = re.sub(r"^\s*eisung\s+", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\b(?:DAM|SZR|KEP|MGE)\b", " ", collapsed)
    collapsed = re.sub(r"\bq[xaieo]_[A-Za-z0-9_]+\b", " ", collapsed)
    collapsed = re.sub(r"(?<![A-Z0-9])[A-Z]\d{1,2}-\d{2}[MEK]\d{1,4}(?:[./_-]\d{1,4})?\b", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"(?<![A-Z0-9])[-=+]?\d{0,3}[MEKQ]\d{1,4}(?:[./_-]\d{1,4})?\b", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"(?<![A-Z0-9])[-=+]?[A-Z]{1,4}\d{1,5}[A-Z]?(?:[./_-]\d{1,4})?\b", " ", collapsed)
    collapsed = re.sub(r"/\d{1,3}(?:[.,]\d{1,2})?", " ", collapsed)
    collapsed = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:kw|w|kva|va|a|v)\b", "", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\b[PIM]\s*=", " ", collapsed)
    collapsed = re.sub(r"\b(?:U1|V1|W1|PE|L1|L2|L3|N|BN|BK|GY|GNYE|WH|GN|YE|RD|BU|A1|A2)\b", " ", collapsed)
    collapsed = re.sub(r"\b\d+\s*~\b", " ", collapsed)
    collapsed = re.sub(r"[_|]+", " ", collapsed)
    collapsed = re.sub(r"\s{2,}", " ", collapsed).strip(" -;|:,")
    collapsed = re.sub(r"^[a-zäöüß]+\s+(?=[A-ZÄÖÜ])", " ", collapsed).strip()
    collapsed = re.sub(r"\s+Re$", "", collapsed).strip()
    return collapsed[:110] if collapsed else "Unbenannter Verbraucher"


def _designation_score(text: str) -> float:
    designation = clean_designation(text)
    if designation == "Unbenannter Verbraucher":
        return -10

    normalized = _normalize_search_text(designation)
    if any(marker in normalized for marker in LINE_NOISE_MARKERS):
        return -8
    if re.search(r"\b(?:\d+(?:x|g)\d+(?:[,.]\d+)?|qc\d*q?-?f|mm²|mm2)\b", normalized, re.IGNORECASE):
        return -6
    if _contains_exclusion(designation) and detect_consumer_type(designation) == "Unklar":
        return -7
    if normalized in {"m", "reserve", "no com", "sockel"}:
        return -6
    if len(re.sub(r"[^A-Za-zÄÖÜäöüß]", "", designation)) < 4:
        return -5

    score = 0.0
    if detect_consumer_type(designation) != "Unklar":
        score += 8
    if POWER_PATTERN.search(text) or CURRENT_PATTERN.search(text) or VOLTAGE_PATTERN.search(text):
        score -= 2
    if any(pattern.search(text) for pattern in PREFERRED_IDENTIFIER_PATTERNS):
        score -= 2
    if re.search(r"\b(?:U1|V1|W1|PE|L1|L2|L3|BN|BK|GY|GNYE)\b", text):
        score -= 2
    word_count = len(re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", designation))
    if 1 <= word_count <= 5:
        score += 1
    elif word_count > 8:
        score -= 1
    if designation.isupper():
        score += 0.5
    return score


def _best_designation(context_lines: list[str], fallback: str) -> str:
    candidates = [(line, _designation_score(line)) for line in context_lines if line.strip()]
    candidates = [candidate for candidate in candidates if candidate[1] > -5]
    if not candidates:
        return clean_designation(fallback)

    best_line, best_score = max(candidates, key=lambda item: item[1])
    best_index = context_lines.index(best_line)
    if best_score <= _designation_score(fallback):
        return clean_designation(fallback)

    designation = clean_designation(best_line)
    if _normalize_search_text(designation) in {"motor", "antrieb"}:
        for neighbor in context_lines[best_index + 1 : best_index + 4]:
            neighbor_designation = clean_designation(neighbor)
            if neighbor_designation != "Unbenannter Verbraucher" and _designation_score(neighbor_designation) >= 0:
                designation = f"{designation} {neighbor_designation}"[:110]
                break
    return designation


def _extract_page_title(lines: list[str]) -> str:
    candidates: list[str] = []
    ignored_single_terms = {"temp", "daten", "takt", "sense", "links", "rechts"}
    for line in lines[-35:]:
        tail = line
        if re.search(r"ursprung:?", line, re.IGNORECASE):
            tail = re.split(r"ursprung:?", line, flags=re.IGNORECASE)[-1]
            tail = re.sub(r"P\.[A-Z0-9.]+", " ", tail, flags=re.IGNORECASE)
        cleaned = clean_designation(tail)
        if cleaned == "Unbenannter Verbraucher":
            continue
        normalized = _normalize_search_text(cleaned)
        if any(marker in normalized for marker in LINE_NOISE_MARKERS):
            continue
        if normalized in ignored_single_terms:
            continue
        if detect_consumer_type(cleaned) != "Unklar" or cleaned.isupper():
            candidates.append(cleaned)

    if not candidates:
        return ""

    return " ".join(candidates[-2:])[:110]


def _consumer_quality(item: dict[str, Any]) -> float:
    designation = str(item.get("designation") or "")
    confidence = _to_float(item.get("confidence")) or 0
    quality = confidence
    if item.get("identifier"):
        quality += 0.08
    if item.get("nominal_power_kw") is not None:
        quality += 0.18
    if designation and designation != "Unbenannter Verbraucher":
        quality += 0.16
    if detect_consumer_type(designation) != "Unklar":
        quality += 0.1
    if _identifier_family(str(item.get("identifier") or "")) in {"M", "E"}:
        quality += 0.06
    return quality


def _consumer_dedupe_key(item: dict[str, Any]) -> tuple[Any, ...]:
    identifier = str(item.get("identifier") or "").strip().upper().lstrip("-+=")
    if identifier:
        return ("identifier", identifier)

    designation = _normalize_search_text(str(item.get("designation") or ""))
    designation = re.sub(r"[^a-z0-9]+", " ", designation).strip()
    power = _to_float(item.get("nominal_power_kw"))
    return ("designation", designation, round(power or 0, 3))


def deduplicate_consumers(consumers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for item in consumers:
        key = _consumer_dedupe_key(item)
        if key not in kept:
            kept[key] = item
            order.append(key)
            continue
        if _consumer_quality(item) > _consumer_quality(kept[key]):
            kept[key] = item

    deduplicated = [kept[key] for key in order]
    strong_load_pages = {
        (item.get("page"), item.get("consumer_type"))
        for item in deduplicated
        if _identifier_family(str(item.get("identifier") or "")) in {"M", "E"}
    }
    strong_designations = [
        re.sub(r"[^a-z0-9]+", "", _normalize_search_text(str(item.get("designation") or "")))
        for item in deduplicated
        if _identifier_family(str(item.get("identifier") or "")) in {"M", "E"}
    ]
    strong_sections = {
        match.group(1).upper()
        for item in deduplicated
        if _identifier_family(str(item.get("identifier") or "")) == "M"
        for match in [re.match(r"([A-Z]\d{1,2}-\d{2})M\d", str(item.get("identifier") or ""), re.IGNORECASE)]
        if match
    }
    deduplicated = [
        item
        for item in deduplicated
        if not (
            _identifier_family(str(item.get("identifier") or "")) == "K"
            and item.get("nominal_power_kw") is None
            and (
                (
                    (section_match := re.match(r"([A-Z]\d{1,2}-\d{2})K\d", str(item.get("identifier") or ""), re.IGNORECASE))
                    and section_match.group(1).upper() in strong_sections
                )
                or
                (item.get("page"), item.get("consumer_type")) in strong_load_pages
                or any(
                    designation
                    and strong
                    and (designation in strong or strong in designation)
                    for designation in [
                        re.sub(r"[^a-z0-9]+", "", _normalize_search_text(str(item.get("designation") or "")))
                    ]
                    for strong in strong_designations
                )
            )
        )
    ]
    for index, item in enumerate(deduplicated, start=1):
        item["detection_id"] = index
    return deduplicated


def extract_consumers_locally(pdf_text: str) -> list[dict[str, Any]]:
    pages = re.split(r"\f+", pdf_text)
    consumers: list[dict[str, Any]] = []

    for page_index, page_text in enumerate(pages, start=1):
        if _page_should_be_skipped(page_text):
            continue

        lines = [line.rstrip() for line in page_text.splitlines() if line.strip()]
        page_title = _extract_page_title(lines)
        aligned_consumers = _extract_column_aligned_consumers(lines, page_index)
        consumers.extend(aligned_consumers)
        aligned_identifiers = {
            str(item.get("identifier") or "").upper()
            for item in aligned_consumers
        }

        for line_index, line in enumerate(lines):
            for match in _iter_local_identifier_matches(line):
                identifier = _normalize_identifier_tag(match.group("tag").strip())
                if identifier.upper() in aligned_identifiers:
                    continue
                if _is_cable_reference_match(line, match):
                    continue
                column_lines = _column_window(lines, line_index, match)
                full_lines = _line_window(lines, line_index, before=3, after=10)
                context = " | ".join(part.strip() for part in column_lines if part.strip())
                snippet = " | ".join(part.strip() for part in full_lines if part.strip())

                consumer_type = detect_consumer_type(context)
                power_kw = extract_power_kw(context)
                current_a = _first_number(CURRENT_PATTERN, context)
                voltage_v = _first_number(VOLTAGE_PATTERN, context)
                designation = _best_designation(column_lines, line)
                designation_type = detect_consumer_type(designation)
                family = _identifier_family(identifier)
                if re.match(r"[A-Z]\d{1,2}-\d{2}[MEK]\d", identifier, re.IGNORECASE) and _designation_score(designation) < 2:
                    full_designation = _best_designation(full_lines, line)
                    if _designation_score(full_designation) > _designation_score(designation):
                        designation = full_designation
                        designation_type = detect_consumer_type(designation)
                if family in {"M", "E"} and page_title and _designation_score(designation) < 2:
                    designation = page_title
                    designation_type = detect_consumer_type(designation)

                if designation_type != "Unklar":
                    consumer_type = designation_type
                if family == "E" and designation_type not in {"Heizung", "Kälte"}:
                    continue
                if family == "K" and designation_type == "Unklar" and power_kw is None:
                    continue
                if family == "K" and power_kw is None and len(re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", designation)) > 5:
                    continue
                if consumer_type == "Unklar" and power_kw is None:
                    continue
                if consumer_type == "Unklar":
                    continue
                if designation == "Unbenannter Verbraucher" and power_kw is None:
                    continue

                confidence = 0.48
                if consumer_type != "Unklar":
                    confidence += 0.18
                if designation != "Unbenannter Verbraucher":
                    confidence += 0.14
                if power_kw is not None:
                    confidence += 0.16
                if current_a is not None or voltage_v is not None:
                    confidence += 0.04
                if family in {"M", "E"}:
                    confidence += 0.04
                if family == "K" and power_kw is None:
                    confidence = min(confidence, 0.72)

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

    return deduplicate_consumers(consumers)


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
- Ignoriere Inhaltsverzeichnisse, Betriebsmittellisten, Klemmenpläne, Stücklisten, Geräteanordnungen und Übersichtstabellen.
- Nutze Verbraucher nur aus dem eigentlichen Stromlaufplan/Schaltplanschema.
- Lies die Bezeichnung aus der unmittelbaren Umgebung des Betriebsmittelkennzeichens oder Symbols, oft direkt darunter.
- Wenn derselbe Verbraucher in einer Übersicht und im Schema vorkommt, gib ihn nur einmal aus der Schema-Fundstelle zurück.

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
Ignoriere Inhaltsverzeichnisse, Betriebsmittellisten, Klemmenpläne, Stücklisten,
Geräteanordnungen und Übersichtstabellen. Nutze Verbraucher nur aus dem eigentlichen
Stromlaufplan/Schaltplanschema und lies Bezeichnungen aus der unmittelbaren Symbolumgebung.
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
        designation = clean_designation(str(item.get("designation") or "Unbenannter Verbraucher"))
        consumer_type = str(item.get("consumer_type") or "").strip()
        if not consumer_type or consumer_type == "Unklar":
            consumer_type = detect_consumer_type(designation)
        normalized.append(
            {
                "detection_id": int(item.get("detection_id") or index),
                "page": int(item.get("page") or 0),
                "identifier": str(item.get("identifier") or "").strip(),
                "designation": designation,
                "consumer_type": consumer_type or "Unklar",
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
    return deduplicate_consumers(normalized)


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
                    "extraction_version": LOCAL_EXTRACTION_VERSION,
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
            "extraction_version": LOCAL_EXTRACTION_VERSION,
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
        "extraction_version": LOCAL_EXTRACTION_VERSION,
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
        "extraction_version": LOCAL_EXTRACTION_VERSION,
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
