import numpy as np
import pandas as pd


def generate_dummy_load_profile() -> pd.DataFrame:
    rng = pd.date_range("2026-01-01 00:00", periods=21 * 24 * 4, freq="15min")
    hours = rng.hour + rng.minute / 60
    weekday = rng.weekday

    base = 68 + np.random.normal(0, 2.5, len(rng))
    shift_load = np.where((weekday < 5) & (hours >= 6) & (hours <= 22), 135, 0)
    saturday_shift = np.where((weekday == 5) & (hours >= 7) & (hours <= 14), 80, 0)
    cycle_a = 34 * (np.sin(np.arange(len(rng)) / 5.2) > 0.35).astype(int)
    cycle_b = 22 * (np.sin(np.arange(len(rng)) / 13.0) > 0.70).astype(int)

    peaks = np.zeros(len(rng))
    for start in [180, 455, 890, 1280, 1680]:
        peaks[start : start + 10] += np.linspace(20, 85, 10)

    power = base + shift_load + saturday_shift + cycle_a + cycle_b + peaks + np.random.normal(0, 4, len(rng))
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
    for candidate in ["timestamp", "time", "datetime", "date", "zeit", "datum", "zeitstempel"]:
        if candidate in lower_cols:
            time_col = lower_cols[candidate]
            break

    power_col = None
    for candidate in ["power_kw", "leistung", "kw", "load", "lastgang", "power", "p"]:
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

    if result.empty:
        raise ValueError("Keine gültigen Zeitstempel-/Leistungsdaten gefunden.")

    return result


def classify_production_window(df: pd.DataFrame) -> pd.Series:
    return (df["weekday"] < 5) & (df["hour_float"] >= 6) & (df["hour_float"] <= 22)


def detect_cycles(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    smooth = result["power_kw"].rolling(8, min_periods=1, center=True).mean()
    threshold = smooth.quantile(0.72)
    result["cycle_active"] = smooth > threshold
    result["cycle_start"] = result["cycle_active"].astype(int).diff().fillna(0).eq(1)
    return result


def build_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    heat = df.copy()
    heat["hour"] = heat["timestamp"].dt.hour
    pivot = heat.pivot_table(index="weekday", columns="hour", values="power_kw", aggfunc="mean")
    pivot = pivot.reindex(index=list(range(7)), columns=list(range(24)))
    pivot.index = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    return pivot


def get_top_peaks(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    peaks = df.nlargest(n, "power_kw")[["timestamp", "power_kw"]].copy()
    peaks["timestamp"] = peaks["timestamp"].dt.strftime("%d.%m.%Y %H:%M")
    peaks.columns = ["Zeitpunkt", "Leistung [kW]"]
    return peaks


def analyze_load_profile(df: pd.DataFrame, production_data: dict, energy_data: dict) -> dict:
    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour
    df["hour_float"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60
    df["weekday"] = df["timestamp"].dt.weekday
    df["date"] = df["timestamp"].dt.date

    median_interval_hours = df["timestamp"].diff().dt.total_seconds().dropna().median() / 3600
    if not np.isfinite(median_interval_hours) or median_interval_hours <= 0:
        median_interval_hours = 0.25

    df["energy_kwh"] = df["power_kw"] * median_interval_hours
    df["is_production_time"] = classify_production_window(df)
    df = detect_cycles(df)

    total_energy = df["energy_kwh"].sum()
    peak_power = df["power_kw"].max()
    base_load = df["power_kw"].quantile(0.1)
    avg_power = df["power_kw"].mean()
    load_factor = avg_power / peak_power if peak_power else 0

    production_energy = df.loc[df["is_production_time"], "energy_kwh"].sum()
    non_production_energy = total_energy - production_energy
    non_production_share = non_production_energy / total_energy if total_energy else 0

    detected_cycles = int(df["cycle_start"].sum())
    cycle_energy = df.loc[df["cycle_active"], "energy_kwh"].sum()
    cycle_energy_share = cycle_energy / total_energy if total_energy else 0

    daily_energy = df.groupby("date")["energy_kwh"].sum().reset_index()
    heatmap_data = build_heatmap_data(df)
    top_peaks = get_top_peaks(df)

    annual_output = production_data.get("annual_output", 100000) or 100000
    analyzed_days = max((df["timestamp"].max() - df["timestamp"].min()).days + 1, 1)
    annualized_energy = total_energy / analyzed_days * 365
    estimated_units_period = annual_output / 365 * analyzed_days
    energy_per_unit = total_energy / max(estimated_units_period, 1)

    price = energy_data.get("electricity_price", 0.22) or 0.22
    peak_price = energy_data.get("peak_price", 120.0) or 120.0

    baseline_saving_rate = min(0.22, max(0.04, non_production_share * 0.42))
    estimated_savings_kwh = total_energy * baseline_saving_rate
    estimated_savings_eur = estimated_savings_kwh * price

    avoidable_peak_kw = max(0, peak_power - df["power_kw"].quantile(0.95))
    peak_savings_eur_year = avoidable_peak_kw * peak_price

    co2_factor_kg_per_kwh = 0.38
    estimated_co2_savings_t = estimated_savings_kwh * co2_factor_kg_per_kwh / 1000

    recommendations = build_recommendations(
        non_production_share=non_production_share,
        load_factor=load_factor,
        base_load=base_load,
        avg_power=avg_power,
        detected_cycles=detected_cycles,
        analyzed_days=analyzed_days,
    )

    return {
        "df": df,
        "total_energy": total_energy,
        "annualized_energy": annualized_energy,
        "peak_power": peak_power,
        "base_load": base_load,
        "avg_power": avg_power,
        "load_factor": load_factor,
        "detected_cycles": detected_cycles,
        "cycle_energy_share": cycle_energy_share,
        "non_production_energy": non_production_energy,
        "non_production_share": non_production_share,
        "energy_per_unit": energy_per_unit,
        "estimated_savings_kwh": estimated_savings_kwh,
        "estimated_savings_eur": estimated_savings_eur,
        "estimated_co2_savings_t": estimated_co2_savings_t,
        "peak_savings_eur_year": peak_savings_eur_year,
        "top_peaks": top_peaks,
        "daily_energy": daily_energy,
        "heatmap_data": heatmap_data,
        "recommendations": recommendations,
        "analyzed_days": analyzed_days,
    }


def build_recommendations(
    non_production_share: float,
    load_factor: float,
    base_load: float,
    avg_power: float,
    detected_cycles: int,
    analyzed_days: int,
) -> list[dict]:
    recommendations = []

    def add(priority: str, title: str, reason: str, impact: str):
        recommendations.append(
            {
                "priority": priority,
                "title": title,
                "reason": reason,
                "impact": impact,
            }
        )

    if non_production_share > 0.25:
        add(
            "hoch",
            "Grundlast außerhalb der Produktion senken",
            "Ein erheblicher Anteil des Energieverbrauchs liegt außerhalb typischer Produktionszeiten.",
            "Abschaltmatrix für Druckluft, Pumpen, Absaugung, Temperierung und Standby-Verbrauch aufbauen.",
        )
    elif non_production_share > 0.15:
        add(
            "mittel",
            "Nicht-Produktionszeiten prüfen",
            "Der Verbrauch außerhalb typischer Produktionszeiten ist relevant, aber nicht extrem.",
            "Wochenend- und Nachtlast getrennt messen und Abschaltfenster definieren.",
        )

    if load_factor < 0.55:
        add(
            "hoch",
            "Lastspitzenmanagement einführen",
            "Der Lastfaktor deutet auf ausgeprägte Leistungsspitzen hin.",
            "Gleichzeitiges Anfahren energieintensiver Anlagen vermeiden und Startsequenzen optimieren.",
        )
    elif load_factor < 0.68:
        add(
            "mittel",
            "Lastspitzen überwachen",
            "Einzelne Spitzen können Leistungspreise erhöhen.",
            "Peak-Alarm im Energiemonitoring einrichten und Hauptverursacher identifizieren.",
        )

    if base_load > avg_power * 0.42:
        add(
            "hoch",
            "Hohe Grundlast technisch auflösen",
            "Die Grundlast ist im Verhältnis zur mittleren Leistung hoch.",
            "Maschinen im Standby, Leckagen im Druckluftsystem und dauerhaft laufende Nebenaggregate priorisieren.",
        )

    if detected_cycles > analyzed_days * 2:
        add(
            "mittel",
            "Zyklusbezogene Energiekennzahlen einführen",
            "Viele wiederkehrende Produktionszyklen wurden im Lastgang erkannt.",
            "Energie pro Zyklus, Produktgruppe oder Charge berechnen und mit Qualitäts-/Ausschussdaten verbinden.",
        )

    if not recommendations:
        add(
            "niedrig",
            "Datenbasis verfeinern",
            "Im aggregierten Lastgang zeigen sich keine starken Auffälligkeiten.",
            "Messung nach Linien, Maschinen oder Medien auflösen, um versteckte Potenziale sichtbar zu machen.",
        )

    priority_order = {"hoch": 0, "mittel": 1, "niedrig": 2}
    return sorted(recommendations, key=lambda item: priority_order[item["priority"]])