from __future__ import annotations

import argparse
import io
import math
import re
import time
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


TARGET_YEAR = 2023
WB_COUNTRIES_URL = "https://api.worldbank.org/v2/country/all"
WB_INDICATOR_URL = "https://api.worldbank.org/v2/country/all/indicator/{indicator}"
HOFSTEDE_URL = (
    "https://geerthofstede.com/wp-content/uploads/2016/08/"
    "6-dimensions-for-website-2015-12-08-0-100.csv"
)
NDGAIN_URL = "https://gain.nd.edu/assets/647440/ndgain_countryindex_2026.zip"
FAOSTAT_FBS_URL = (
    "https://fenixservices.fao.org/faostat/static/bulkdownloads/"
    "FoodBalanceSheets_E_All_Data.zip"
)
WORLD_MINING_DATA_URL = (
    "https://www.bmf.gv.at/dam/jcr:ed3d811d-6edd-4bf9-b564-40cacaedac94/"
    "6.4.%20Production_of_Mineral_Raw_Materials_of_individual_Countries_by_Minerals.xlsx"
)
TIMEOUT = 60
SESSION = requests.Session()
SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
    ),
)

SOURCE_COLUMNS = {
    "gdp_usd_current": "NY.GDP.MKTP.CD",
    "population": "SP.POP.TOTL",
    "fx_reserves_usd": "FI.RES.XGLD.CD",
    "public_debt_pct_gdp": "GC.DOD.TOTL.GD.ZS",
    "co2_mtco2e": "EN.GHG.CO2.MT.CE.AR5",
    "inequality_gini": "SI.POV.GINI",
    "water_stress_pct": "ER.H2O.FWST.ZS",
    "military_gdp_ratio": "MS.MIL.XPND.GD.ZS",
    "military_spending_usd": "MS.MIL.XPND.CD",
    "wgi_pv": "PV.EST",
    "wgi_ge": "GE.EST",
    "wgi_rl": "RL.EST",
    "wgi_va": "VA.EST",
    "rd_pct_gdp": "GB.XPD.RSDV.GD.ZS",
    "high_tech_exports_pct": "TX.VAL.TECH.MF.ZS",
    "manufacturing_share_pct": "NV.IND.MANF.ZS",
    "energy_use_kg_oe_pc": "EG.USE.PCAP.KG.OE",
    "energy_imports_net_pct": "EG.IMP.CONS.ZS",
    "agri_share_pct": "NV.AGR.TOTL.ZS",
    "food_production_index": "AG.PRD.FOOD.XD",
    "arable_land_pct": "AG.LND.ARBL.ZS",
    "coal_rents_pct": "NY.GDP.COAL.RT.ZS",
    "gas_rents_pct": "NY.GDP.NGAS.RT.ZS",
    "oil_rents_pct": "NY.GDP.PETR.RT.ZS",
    "mineral_rents_pct": "NY.GDP.MINR.RT.ZS",
}

OUTPUT_COLUMNS = [
    "id",
    "name",
    "region",
    "regime_type",
    "alliance_block",
    "gdp",
    "population",
    "fx_reserves",
    "public_debt_pct_gdp",
    "energy_reserve",
    "energy_production",
    "energy_consumption",
    "food_reserve",
    "food_production",
    "food_consumption",
    "metals_reserve",
    "metals_production",
    "metals_consumption",
    "trust_gov",
    "social_tension",
    "inequality_gini",
    "climate_risk",
    "co2_annual_emissions",
    "biodiversity_local",
    "pdi",
    "idv",
    "mas",
    "uai",
    "lto",
    "ind",
    "traditional_secular",
    "survival_self_expression",
    "tech_level",
    "security_index",
    "military_power",
    "water_stress",
    "regime_stability",
    "debt_crisis_prone",
    "conflict_proneness",
]

IMPUTED_SOURCE_COLUMNS = [
    "gdp_usd_current",
    "population",
    "fx_reserves_usd",
    "public_debt_pct_gdp",
    "co2_mtco2e",
    "inequality_gini",
    "water_stress_pct",
    "military_gdp_ratio",
    "military_spending_usd",
    "wgi_pv",
    "wgi_ge",
    "wgi_rl",
    "wgi_va",
    "rd_pct_gdp",
    "high_tech_exports_pct",
    "manufacturing_share_pct",
    "energy_use_kg_oe_pc",
    "energy_imports_net_pct",
    "agri_share_pct",
    "food_production_index",
    "arable_land_pct",
    "coal_rents_pct",
    "gas_rents_pct",
    "oil_rents_pct",
    "mineral_rents_pct",
    "climate_vulnerability",
    "habitat_vulnerability",
    "ecosystem_vulnerability",
    "ndgain_governance_readiness",
    "pdi",
    "idv",
    "mas",
    "uai",
    "lto",
    "ind",
    "energy_production_raw",
    "energy_consumption_raw",
    "energy_reserve_raw",
    "food_production_raw",
    "food_consumption_raw",
    "food_reserve_raw",
    "metals_production_raw",
    "metals_consumption_raw",
    "metals_reserve_raw",
]

IMPUTED_DERIVED_COLUMNS = [
    "gdp_per_capita",
    "fx_to_gdp",
    "water_stress",
    "climate_risk",
    "biodiversity_local",
    "regime_stability",
    "trust_gov",
    "social_tension",
    "security_index",
    "tech_level",
    "military_power",
    "debt_crisis_prone",
    "conflict_proneness",
    "traditional_secular",
    "survival_self_expression",
    "energy_production_raw",
    "energy_consumption_raw",
    "energy_reserve_raw",
    "food_production_raw",
    "food_consumption_raw",
    "food_reserve_raw",
    "metals_production_raw",
    "metals_consumption_raw",
    "metals_reserve_raw",
    "energy_reserve",
    "energy_production",
    "energy_consumption",
    "food_reserve",
    "food_production",
    "food_consumption",
    "metals_reserve",
    "metals_production",
    "metals_consumption",
]

NON_SOVEREIGN_OK = {"HKG", "MAC"}
PACIFIC_OCEANIA = {
    "AUS",
    "NZL",
    "FJI",
    "PNG",
    "SLB",
    "VUT",
    "WSM",
    "KIR",
    "TON",
    "FSM",
    "PLW",
    "MHL",
    "NRU",
    "TUV",
}
SOUTH_ASIA = {"AFG", "BGD", "BTN", "IND", "LKA", "MDV", "NPL", "PAK"}
NORTH_AMERICA = {"USA", "CAN", "MEX"}
MIDDLE_EAST = {
    "ARE",
    "BHR",
    "DZA",
    "EGY",
    "IRN",
    "IRQ",
    "ISR",
    "JOR",
    "KWT",
    "LBN",
    "LBY",
    "MAR",
    "OMN",
    "QAT",
    "SAU",
    "SYR",
    "TUN",
    "TUR",
    "YEM",
}
EUROPE_EXTENDED = {
    "ALB",
    "AND",
    "AUT",
    "BEL",
    "BGR",
    "BIH",
    "BLR",
    "CHE",
    "CYP",
    "CZE",
    "DEU",
    "DNK",
    "ESP",
    "EST",
    "FIN",
    "FRA",
    "GBR",
    "GRC",
    "HRV",
    "HUN",
    "IRL",
    "ISL",
    "ITA",
    "LTU",
    "LUX",
    "LVA",
    "MDA",
    "MKD",
    "MLT",
    "MNE",
    "NLD",
    "NOR",
    "POL",
    "PRT",
    "ROU",
    "RUS",
    "SRB",
    "SVK",
    "SVN",
    "SWE",
    "UKR",
}
RESIDUAL_DEFAULTS = {
    "Europe": ("Rest of Europe", "Western", "Mixed"),
    "North America": ("Rest of North America", "Western", "Mixed"),
    "East Asia": ("Rest of East Asia", "NonAligned", "Mixed"),
    "South Asia": ("Rest of South Asia", "IndoPacific", "Mixed"),
    "South America": ("Rest of South America", "Latin", "Mixed"),
    "Middle East": ("Rest of Middle East", "MENA", "Mixed"),
    "Oceania": ("Rest of Oceania", "Western", "Mixed"),
    "Global South": ("Rest of Global South", "NonAligned", "Mixed"),
}
RESOURCE_WORLD_TOTALS = {
    "energy_consumption": 14800.0,
    "food_consumption": 820.0,
    "metals_production": 350.0,
    "metals_consumption": 1650.0,
}
FOOD_GROUP_ITEMS = {
    "Animal fats",
    "Cereals - Excluding Beer",
    "Eggs",
    "Fish, Seafood",
    "Fruits - Excluding Wine",
    "Meat",
    "Milk - Excluding Butter",
    "Offals",
    "Oilcrops",
    "Pulses",
    "Starchy Roots",
    "Sugar & Sweeteners",
    "Treenuts",
    "Vegetable Oils",
    "Vegetables",
}
FOOD_ELEMENTS = {"Production", "Food", "Domestic supply quantity", "Stock Variation"}
WMD_ENERGY_FACTORS = {
    "Steam Coal ": 0.00000070,
    "Coking Coal": 0.00000080,
    "Lignite": 0.00000035,
    "Natural Gas": 0.0009,
    "Petroleum": 0.00000102,
}
WMD_METAL_WEIGHTS = {
    "Iron (Fe)": 0.16,
    "Copper": 0.12,
    "Aluminium": 0.10,
    "Bauxite": 0.04,
    "Nickel": 0.08,
    "Zinc": 0.08,
    "Lead": 0.05,
    "Tin": 0.03,
    "Lithium (Li2O)": 0.08,
    "Cobalt": 0.08,
    "Manganese": 0.06,
    "Chromium (Cr2O3)": 0.05,
    "Gold": 0.03,
    "Silver": 0.02,
    "Platinum": 0.02,
}
COUNTRY_NAME_ALIASES = {
    "bahamas": "BHS",
    "bolivia": "BOL",
    "bosnia herzegovina": "BIH",
    "bosnia and herzegovina": "BIH",
    "bosniaherzegovina": "BIH",
    "brunei": "BRN",
    "cape verde": "CPV",
    "china hong kong sar": "HKG",
    "china hong kong special administrative region": "HKG",
    "china macao sar": "MAC",
    "china mainland": "CHN",
    "china taiwan": "TWN",
    "china taiwan province of": "TWN",
    "congo dem rep": "COD",
    "congo democratic republic of the": "COD",
    "congo kinshasa": "COD",
    "congo republic of": "COG",
    "congo brazzaville": "COG",
    "czech republic": "CZE",
    "democratic peoples republic of korea": "PRK",
    "democratic republic of the congo": "COD",
    "egypt": "EGY",
    "egypt arab rep": "EGY",
    "eswatini": "SWZ",
    "gambia": "GMB",
    "hong kong sar": "HKG",
    "hong kong sar china": "HKG",
    "hong kong": "HKG",
    "iran": "IRN",
    "iran islamic republic of": "IRN",
    "ivory coast": "CIV",
    "korea dem peoples rep": "PRK",
    "korea republic of": "KOR",
    "korea rep": "KOR",
    "kyrgyz republic": "KGZ",
    "lao pdr": "LAO",
    "macao sar": "MAC",
    "macao sar china": "MAC",
    "macao": "MAC",
    "micronesia fed sts": "FSM",
    "moldova": "MDA",
    "north korea": "PRK",
    "north macedonia": "MKD",
    "palestine": "PSE",
    "republic of korea": "KOR",
    "russian federation": "RUS",
    "slovak republic": "SVK",
    "south korea": "KOR",
    "st kitts and nevis": "KNA",
    "st lucia": "LCA",
    "st vincent and the grenadines": "VCT",
    "syrian arab republic": "SYR",
    "taiwan": "TWN",
    "taiwan province of china": "TWN",
    "the bahamas": "BHS",
    "the gambia": "GMB",
    "turkey": "TUR",
    "turkiye": "TUR",
    "u s a": "USA",
    "united states": "USA",
    "united states of america": "USA",
    "venezuela": "VEN",
    "venezuela rb": "VEN",
    "viet nam": "VNM",
    "yemen rep": "YEM",
}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def robust_minmax(series: pd.Series, *, lower_q: float = 0.05, upper_q: float = 0.95, default: float = 0.5) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return pd.Series(default, index=series.index, dtype=float)
    lo = numeric.quantile(lower_q)
    hi = numeric.quantile(upper_q)
    if pd.isna(lo) or pd.isna(hi) or hi <= lo:
        return pd.Series(default, index=series.index, dtype=float)
    clipped = numeric.clip(lower=lo, upper=hi)
    return ((clipped - lo) / (hi - lo)).fillna(default)


def weighted_average(group: pd.DataFrame, column: str, weight_column: str) -> float:
    values = pd.to_numeric(group[column], errors="coerce")
    weights = pd.to_numeric(group[weight_column], errors="coerce")
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return float("nan")
    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def normalize_country_name(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(the|of|special administrative region|islamic republic|plurinational state)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_country_name_lookup(frame: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for _, row in frame.iterrows():
        iso3 = row.get("iso3")
        if pd.isna(iso3):
            continue
        for column in ["name", "ndgain_name"]:
            candidate = normalize_country_name(row.get(column))
            if candidate:
                lookup[candidate] = str(iso3)
    for source_name, iso3 in COUNTRY_NAME_ALIASES.items():
        candidate = normalize_country_name(source_name)
        if candidate:
            lookup.setdefault(candidate, iso3)
    for _, row in frame.iterrows():
        iso3 = row.get("iso3")
        if pd.isna(iso3):
            continue
        candidate = normalize_country_name(row.get("hofstede_name"))
        if candidate:
            lookup.setdefault(candidate, str(iso3))
    return lookup


def map_country_names(frame: pd.DataFrame, source_column: str, lookup: dict[str, str]) -> pd.DataFrame:
    mapped = frame.copy()
    mapped["iso3"] = mapped[source_column].map(lambda value: lookup.get(normalize_country_name(value)))
    return mapped


def request_json(url: str, *, params: dict[str, object] | None = None) -> list[object]:
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = SESSION.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError(f"Unexpected response from {url}")
            return data
        except Exception as exc:  # pragma: no cover - network variability
            last_error = exc
            if attempt == 5:
                raise
            time.sleep(attempt)
    assert last_error is not None
    raise last_error


def download_bytes(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = SESSION.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.content
        except Exception as exc:  # pragma: no cover - network variability
            last_error = exc
            if attempt == 5:
                raise
            time.sleep(attempt)
    assert last_error is not None
    raise last_error


def cached_download(url: str, path: Path) -> bytes:
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = download_bytes(url)
    path.write_bytes(payload)
    return payload


def fetch_country_metadata() -> pd.DataFrame:
    payload = request_json(WB_COUNTRIES_URL, params={"format": "json", "per_page": 400})
    rows = payload[1] or []
    records: list[dict[str, object]] = []
    for row in rows:
        region = (row.get("region") or {}).get("value")
        if region == "Aggregates":
            continue
        records.append(
            {
                "iso3": row["id"],
                "iso2": row["iso2Code"],
                "name": row["name"],
                "wb_region": region,
                "income_level": (row.get("incomeLevel") or {}).get("value"),
            }
        )
    return pd.DataFrame.from_records(records)


def fetch_indicator(indicator: str, target_year: int = TARGET_YEAR, start_year: int = 2014) -> pd.DataFrame:
    payload = request_json(
        WB_INDICATOR_URL.format(indicator=indicator),
        params={"format": "json", "per_page": 20000, "date": f"{start_year}:{target_year}"},
    )
    rows = payload[1] or []
    records: list[dict[str, object]] = []
    for row in rows:
        value = row.get("value")
        year_raw = row.get("date")
        iso3 = row.get("countryiso3code")
        if value is None or not iso3 or iso3 == "NA":
            continue
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            continue
        if year > target_year:
            continue
        records.append({"iso3": iso3, "name": row["country"]["value"], "year": year, "value": float(value)})
    if not records:
        return pd.DataFrame(columns=["iso3", "value", "source_year", "source_kind"])
    frame = pd.DataFrame.from_records(records).sort_values(["iso3", "year"], ascending=[True, False])
    latest = frame.groupby("iso3", as_index=False).first()
    latest["source_year"] = latest["year"].astype(int)
    latest["source_kind"] = latest["source_year"].map(
        lambda year: "direct_2023" if year == target_year else f"latest_{year}"
    )
    return latest[["iso3", "value", "source_year", "source_kind"]]


def load_hofstede(cache_dir: Path) -> pd.DataFrame:
    payload = cached_download(HOFSTEDE_URL, cache_dir / "hofstede_6_dimensions.csv")
    frame = pd.read_csv(io.StringIO(payload.decode("utf-8")), sep=";")
    frame = frame.rename(
        columns={
            "ctr": "iso3",
            "country": "hofstede_name",
            "ltowvs": "lto",
            "ivr": "ind",
        }
    )
    frame["iso3"] = frame["iso3"].replace({"TAI": "TWN"})
    columns = ["pdi", "idv", "mas", "uai", "lto", "ind"]
    for column in columns:
        frame[column] = pd.to_numeric(frame[column].replace("#NULL!", pd.NA), errors="coerce")
    frame["hofstede_source"] = frame[columns].notna().all(axis=1).map(
        lambda ok: "direct_hofstede" if ok else "partial_hofstede"
    )
    return frame[["iso3", "hofstede_name", *columns, "hofstede_source"]]


def load_ndgain(cache_dir: Path) -> pd.DataFrame:
    payload = cached_download(NDGAIN_URL, cache_dir / "ndgain_countryindex_2026.zip")
    archive = zipfile.ZipFile(io.BytesIO(payload))

    def extract_member(path: str, value_name: str) -> pd.DataFrame:
        with archive.open(path) as member:
            frame = pd.read_csv(member)
        return frame[["ISO3", "Name", str(TARGET_YEAR)]].rename(
            columns={"ISO3": "iso3", "Name": "ndgain_name", str(TARGET_YEAR): value_name}
        )

    vulnerability = extract_member("resources/vulnerability/vulnerability.csv", "climate_vulnerability")
    habitat = extract_member("resources/vulnerability/habitat.csv", "habitat_vulnerability")
    ecosystems = extract_member("resources/vulnerability/ecosystems.csv", "ecosystem_vulnerability")
    governance = extract_member("resources/readiness/governance.csv", "ndgain_governance_readiness")

    merged = vulnerability.merge(habitat, on=["iso3", "ndgain_name"], how="outer")
    merged = merged.merge(ecosystems, on=["iso3", "ndgain_name"], how="outer")
    merged = merged.merge(governance, on=["iso3", "ndgain_name"], how="outer")
    merged["ndgain_source"] = merged["climate_vulnerability"].notna().map(
        lambda ok: "direct_ndgain" if ok else "missing_ndgain"
    )
    return merged


def load_overrides(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    numeric_columns = [
        "gdp_usd_current",
        "population",
        "fx_reserves_usd",
        "public_debt_pct_gdp",
        "co2_mtco2e",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def guess_model_region(row: pd.Series) -> str:
    iso3 = row["iso3"]
    wb_region = row.get("wb_region")
    if iso3 in PACIFIC_OCEANIA:
        return "Oceania"
    if iso3 in NORTH_AMERICA:
        return "North America"
    if iso3 in SOUTH_ASIA:
        return "South Asia"
    if iso3 in MIDDLE_EAST:
        return "Middle East"
    if iso3 in EUROPE_EXTENDED:
        return "Europe"
    if wb_region == "Latin America & Caribbean":
        return "South America"
    if wb_region == "East Asia & Pacific":
        return "East Asia"
    if wb_region == "Sub-Saharan Africa":
        return "Global South"
    if wb_region == "Europe & Central Asia":
        return "Global South"
    if wb_region == "Middle East & North Africa":
        return "Middle East"
    if wb_region == "South Asia":
        return "South Asia"
    return "Global South"


def default_alliance(row: pd.Series) -> str:
    iso3 = row["iso3"]
    region = row["model_region"]
    if iso3 in {"CHN", "RUS", "BLR", "IRN", "HKG", "MAC"}:
        return "Eurasian"
    if region == "South America":
        return "Latin"
    if region == "Middle East":
        return "MENA"
    if region in {"North America", "Europe", "Oceania"} or iso3 in {"JPN", "KOR", "ISR", "TWN"}:
        return "Western"
    if iso3 in {"IND", "IDN", "VNM", "THA", "MYS", "PHL", "SGP"}:
        return "IndoPacific"
    return "NonAligned"


def default_regime(row: pd.Series) -> str:
    va = row.get("wgi_va_unit")
    rl = row.get("wgi_rl_unit")
    if pd.isna(va) or pd.isna(rl):
        return "Hybrid"
    if va >= 0.65 and rl >= 0.55:
        return "Democracy"
    if va <= 0.35 and rl <= 0.45:
        return "Autocracy"
    return "Hybrid"


def apply_overrides(frame: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "gdp_usd_current",
        "population",
        "fx_reserves_usd",
        "public_debt_pct_gdp",
        "co2_mtco2e",
    ]
    textual_columns = ["name", "model_region", "alliance_block", "regime_type"]

    base = frame.drop(columns=[column for column in frame.columns if column.startswith("override_")], errors="ignore")
    merged = base.merge(
        overrides.rename(columns={column: f"override_{column}" for column in overrides.columns if column != "iso3"}),
        on="iso3",
        how="left",
    )

    for column in numeric_columns:
        override_column = f"override_{column}"
        source_column = f"src_{column}"
        if override_column not in merged.columns:
            continue
        mask = merged[override_column].notna()
        merged.loc[mask, column] = merged.loc[mask, override_column]
        merged.loc[mask, source_column] = "manual_override"

    for column in textual_columns:
        override_column = f"override_{column}"
        if override_column not in merged.columns:
            continue
        mask = merged[override_column].fillna("").astype(str).str.strip() != ""
        merged.loc[mask, column] = merged.loc[mask, override_column]

    return merged


def fill_by_region(frame: pd.DataFrame, column: str, *, strategy: str = "median", default_value: float | None = None) -> None:
    if strategy == "zero":
        missing = frame[column].isna()
        frame.loc[missing, column] = 0.0 if default_value is None else default_value
        frame.loc[missing, f"src_{column}"] = "zero_imputed"
        return

    if strategy == "mean":
        region_fill = frame.groupby("model_region")[column].transform("mean")
        global_fill = frame[column].mean()
        label = "region_mean_imputed"
    else:
        region_fill = frame.groupby("model_region")[column].transform("median")
        global_fill = frame[column].median()
        label = "region_median_imputed"

    if default_value is not None and pd.isna(global_fill):
        global_fill = default_value

    missing = frame[column].isna()
    fill_values = region_fill.fillna(global_fill)
    if default_value is not None:
        fill_values = fill_values.fillna(default_value)
    frame.loc[missing, column] = fill_values[missing]
    frame.loc[missing, f"src_{column}"] = label


def fill_per_capita_by_region(
    frame: pd.DataFrame,
    column: str,
    *,
    population_column: str = "population",
    default_per_capita: float = 0.0,
) -> None:
    denominator = pd.to_numeric(frame[population_column], errors="coerce").clip(lower=1.0)
    per_capita = pd.to_numeric(frame[column], errors="coerce") / denominator
    region_fill = per_capita.groupby(frame["model_region"]).transform("median")
    global_fill = per_capita.median()
    if pd.isna(global_fill):
        global_fill = default_per_capita
    fill_per_capita = region_fill.fillna(global_fill).fillna(default_per_capita)
    missing = frame[column].isna()
    frame.loc[missing, column] = fill_per_capita[missing] * denominator[missing]
    frame.loc[missing, f"src_{column}"] = "region_per_capita_imputed"


def fill_ratio_by_region(
    frame: pd.DataFrame,
    column: str,
    denominator: pd.Series,
    *,
    default_ratio: float = 0.0,
) -> None:
    safe_denominator = pd.to_numeric(denominator, errors="coerce").clip(lower=1e-9)
    ratio = pd.to_numeric(frame[column], errors="coerce") / safe_denominator
    region_fill = ratio.groupby(frame["model_region"]).transform("median")
    global_fill = ratio.median()
    if pd.isna(global_fill):
        global_fill = default_ratio
    fill_ratio = region_fill.fillna(global_fill).fillna(default_ratio)
    missing = frame[column].isna()
    frame.loc[missing, column] = fill_ratio[missing] * safe_denominator[missing]
    frame.loc[missing, f"src_{column}"] = "region_ratio_imputed"


def load_faostat_food_balance(cache_dir: Path, lookup: dict[str, str]) -> pd.DataFrame:
    payload = cached_download(FAOSTAT_FBS_URL, cache_dir / "FoodBalanceSheets_E_All_Data.zip")
    archive = zipfile.ZipFile(io.BytesIO(payload))
    members = [name for name in archive.namelist() if name.endswith("FoodBalanceSheets_E_All_Data.csv")]
    if not members:
        return pd.DataFrame(
            columns=[
                "iso3",
                "food_production_raw",
                "food_consumption_raw",
                "food_domestic_supply_raw",
                "food_stock_variation_raw",
                "src_food_production_raw",
                "src_food_consumption_raw",
            ]
        )

    chunks: list[pd.DataFrame] = []
    with archive.open(members[0]) as member:
        for chunk in pd.read_csv(member, chunksize=100000):
            mask = chunk["Item"].isin(FOOD_GROUP_ITEMS) & chunk["Element"].isin(FOOD_ELEMENTS)
            if not mask.any():
                continue
            subset = chunk.loc[mask, ["Area", "Item", "Element", "Unit", f"Y{TARGET_YEAR}"]].copy()
            subset = subset[subset["Unit"] == "1000 t"]
            subset = subset.drop_duplicates(subset=["Area", "Item", "Element"])
            chunks.append(subset)

    if not chunks:
        return pd.DataFrame(
            columns=[
                "iso3",
                "food_production_raw",
                "food_consumption_raw",
                "food_domestic_supply_raw",
                "food_stock_variation_raw",
                "src_food_production_raw",
                "src_food_consumption_raw",
            ]
        )

    combined = pd.concat(chunks, ignore_index=True)
    combined = map_country_names(combined, "Area", lookup)
    combined = combined[combined["iso3"].notna()].copy()
    combined[f"Y{TARGET_YEAR}"] = pd.to_numeric(combined[f"Y{TARGET_YEAR}"], errors="coerce")
    grouped = (
        combined.groupby(["iso3", "Element"], as_index=False)[f"Y{TARGET_YEAR}"]
        .sum(min_count=1)
        .pivot(index="iso3", columns="Element", values=f"Y{TARGET_YEAR}")
        .reset_index()
    )
    grouped.columns.name = None
    grouped = grouped.rename(
        columns={
            "Production": "food_production_raw",
            "Food": "food_consumption_raw",
            "Domestic supply quantity": "food_domestic_supply_raw",
            "Stock Variation": "food_stock_variation_raw",
        }
    )
    grouped["src_food_production_raw"] = grouped["food_production_raw"].notna().map(
        lambda ok: "direct_faostat_fbs_2023" if ok else pd.NA
    )
    grouped["src_food_consumption_raw"] = grouped["food_consumption_raw"].notna().map(
        lambda ok: "direct_faostat_fbs_2023" if ok else pd.NA
    )
    return grouped


def load_wmd_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=sheet_name, header=1)
    frame = frame.rename(
        columns={
            frame.columns[0]: "country",
            frame.columns[1]: "unit",
            frame.columns[2]: "y2019",
            frame.columns[3]: "y2020",
            frame.columns[4]: "y2021",
            frame.columns[5]: "y2022",
            frame.columns[6]: "y2023",
            frame.columns[7]: "data_source",
        }
    )
    frame = frame[frame["country"].notna()].copy()
    frame["country"] = frame["country"].astype(str).str.strip()
    frame = frame[~frame["country"].str.contains("world|total", case=False, na=False)]
    frame["y2023"] = pd.to_numeric(frame["y2023"], errors="coerce")
    frame = frame[frame["y2023"].notna()].copy()
    return frame[["country", "unit", "y2023"]]


def load_world_mining_data(cache_dir: Path, lookup: dict[str, str]) -> pd.DataFrame:
    cached_download(WORLD_MINING_DATA_URL, cache_dir / "world_mining_data_2025_minerals.xlsx")
    workbook = cache_dir / "world_mining_data_2025_minerals.xlsx"

    energy_rows: list[pd.DataFrame] = []
    for sheet_name, factor in WMD_ENERGY_FACTORS.items():
        frame = load_wmd_sheet(workbook, sheet_name)
        frame = map_country_names(frame, "country", lookup)
        frame = frame[frame["iso3"].notna()].copy()
        frame["energy_component_mtoe"] = frame["y2023"] * factor
        energy_rows.append(frame[["iso3", "energy_component_mtoe"]])

    energy_concat = pd.concat(energy_rows, ignore_index=True) if energy_rows else pd.DataFrame(columns=["iso3", "energy_component_mtoe"])
    energy = (
        energy_concat.groupby("iso3", as_index=False)["energy_component_mtoe"]
        .sum(min_count=1)
        .rename(columns={"energy_component_mtoe": "wmd_energy_production_raw"})
    )
    energy["src_wmd_energy_production_raw"] = energy["wmd_energy_production_raw"].notna().map(
        lambda ok: "direct_wmd_2023" if ok else pd.NA
    )

    metal_components: list[pd.DataFrame] = []
    for sheet_name, weight in WMD_METAL_WEIGHTS.items():
        frame = load_wmd_sheet(workbook, sheet_name)
        frame = map_country_names(frame, "country", lookup)
        frame = frame[frame["iso3"].notna()].copy()
        total = frame["y2023"].sum()
        if total <= 0:
            continue
        frame["metals_component_raw"] = weight * frame["y2023"] / total
        metal_components.append(frame[["iso3", "metals_component_raw"]])

    if metal_components:
        metals = (
            pd.concat(metal_components, ignore_index=True)
            .groupby("iso3", as_index=False)["metals_component_raw"]
            .sum(min_count=1)
            .rename(columns={"metals_component_raw": "wmd_metals_production_raw"})
        )
    else:
        metals = pd.DataFrame(columns=["iso3", "wmd_metals_production_raw"])
    metals["src_wmd_metals_production_raw"] = metals["wmd_metals_production_raw"].notna().map(
        lambda ok: "direct_wmd_2023" if ok else pd.NA
    )
    return energy.merge(metals, on="iso3", how="outer")


def attach_resource_layer(panel: pd.DataFrame, data_root: Path) -> pd.DataFrame:
    cache_dir = data_root / "cache"
    enriched = panel.copy()
    lookup = build_country_name_lookup(enriched)

    food = load_faostat_food_balance(cache_dir, lookup)
    enriched = enriched.merge(food, on="iso3", how="left")

    mining = load_world_mining_data(cache_dir, lookup)
    enriched = enriched.merge(mining, on="iso3", how="left")

    enriched["energy_consumption_raw"] = (
        pd.to_numeric(enriched["energy_use_kg_oe_pc"], errors="coerce")
        * pd.to_numeric(enriched["population"], errors="coerce")
        / 1e9
    )
    enriched["src_energy_consumption_raw"] = enriched["src_energy_use_kg_oe_pc"].fillna(
        "derived_from_energy_use_pc"
    )

    balance_production = (
        enriched["energy_consumption_raw"]
        * (1.0 - pd.to_numeric(enriched["energy_imports_net_pct"], errors="coerce").clip(-250.0, 250.0) / 100.0)
    ).clip(lower=0.0)
    enriched["energy_production_raw"] = balance_production
    enriched["src_energy_production_raw"] = "derived_wb_energy_balance"
    wmd_mask = pd.to_numeric(enriched["wmd_energy_production_raw"], errors="coerce").notna()
    enriched.loc[wmd_mask, "energy_production_raw"] = enriched.loc[wmd_mask, ["wmd_energy_production_raw", "energy_production_raw"]].max(axis=1)
    enriched.loc[wmd_mask, "src_energy_production_raw"] = "direct_wmd_2023_plus_wb_balance"

    direct_food_prod = enriched["food_production_raw"].notna()
    direct_food_cons = enriched["food_consumption_raw"].notna()
    fill_per_capita_by_region(enriched, "food_production_raw")
    fill_per_capita_by_region(enriched, "food_consumption_raw")
    fill_per_capita_by_region(enriched, "food_domestic_supply_raw")
    fill_ratio_by_region(
        enriched,
        "food_stock_variation_raw",
        denominator=enriched["food_domestic_supply_raw"].clip(lower=1e-6),
        default_ratio=0.0,
    )
    enriched.loc[direct_food_prod, "src_food_production_raw"] = "direct_faostat_fbs_2023"
    enriched.loc[direct_food_cons, "src_food_consumption_raw"] = "direct_faostat_fbs_2023"

    positive_stock = pd.to_numeric(enriched["food_stock_variation_raw"], errors="coerce").clip(lower=0.0)
    food_surplus_ratio = (
        (pd.to_numeric(enriched["food_production_raw"], errors="coerce") - pd.to_numeric(enriched["food_consumption_raw"], errors="coerce"))
        / pd.to_numeric(enriched["food_consumption_raw"], errors="coerce").clip(lower=1e-6)
    ).clip(lower=0.0, upper=4.0)
    food_stock_ratio = (
        positive_stock / pd.to_numeric(enriched["food_domestic_supply_raw"], errors="coerce").clip(lower=1e-6)
    ).clip(lower=0.0, upper=1.5)
    food_reserve_years = (0.08 + 0.75 * food_stock_ratio + 0.35 * food_surplus_ratio).clip(0.03, 3.0)
    enriched["food_reserve_raw"] = enriched["food_consumption_raw"] * food_reserve_years
    enriched["src_food_reserve_raw"] = "derived_faostat_buffer"

    metals_direct = pd.to_numeric(enriched["wmd_metals_production_raw"], errors="coerce")
    enriched["metals_production_raw"] = metals_direct.fillna(0.0)
    enriched["src_metals_production_raw"] = metals_direct.notna().map(
        lambda ok: "direct_wmd_2023" if ok else "zero_imputed_no_wmd_production"
    )

    high_tech_norm = robust_minmax(enriched["high_tech_exports_pct"])
    manufacturing_gdp = (
        pd.to_numeric(enriched["gdp_usd_current"], errors="coerce")
        * pd.to_numeric(enriched["manufacturing_share_pct"], errors="coerce").clip(lower=0.0)
        / 100.0
        * (0.7 + 0.3 * high_tech_norm)
    )
    total_manufacturing_gdp = manufacturing_gdp.sum()
    if total_manufacturing_gdp <= 0:
        enriched["metals_consumption_raw"] = 0.0
    else:
        enriched["metals_consumption_raw"] = manufacturing_gdp / total_manufacturing_gdp
    enriched["src_metals_consumption_raw"] = "derived_wb_manufacturing_demand"

    fossil_norm = robust_minmax(enriched["fossil_rents_pct"])
    energy_export_margin = (
        pd.to_numeric(enriched["energy_production_raw"], errors="coerce")
        / pd.to_numeric(enriched["energy_consumption_raw"], errors="coerce").clip(lower=1e-6)
        - 1.0
    ).clip(lower=0.0, upper=4.0)
    energy_reserve_years = (0.35 + 14.0 * fossil_norm + 4.0 * energy_export_margin).clip(0.1, 25.0)
    enriched["energy_reserve_raw"] = enriched["energy_production_raw"] * energy_reserve_years
    enriched["src_energy_reserve_raw"] = "derived_wmd_wb_reserve_proxy"

    mineral_norm = robust_minmax(enriched["mineral_rents_pct"])
    metals_prod_norm = robust_minmax(enriched["metals_production_raw"])
    metals_reserve_years = (0.25 + 14.0 * mineral_norm + 6.0 * metals_prod_norm).clip(0.1, 20.0)
    enriched["metals_reserve_raw"] = enriched["metals_production_raw"] * metals_reserve_years
    enriched["src_metals_reserve_raw"] = "derived_wmd_wb_reserve_proxy"

    return enriched


def build_country_panel(data_root: Path) -> pd.DataFrame:
    cache_dir = data_root / "cache"
    metadata = fetch_country_metadata()

    panel = metadata.copy()
    for column, indicator in SOURCE_COLUMNS.items():
        latest = fetch_indicator(indicator).rename(
            columns={
                "value": column,
                "source_year": f"{column}_source_year",
                "source_kind": f"src_{column}",
            }
        )
        panel = panel.merge(latest, on="iso3", how="left")

    ndgain = load_ndgain(cache_dir)
    panel = panel.merge(ndgain, on="iso3", how="left")
    hofstede = load_hofstede(cache_dir)
    panel = panel.merge(hofstede, on="iso3", how="left")
    for column in ["climate_vulnerability", "habitat_vulnerability", "ecosystem_vulnerability", "ndgain_governance_readiness"]:
        panel[f"src_{column}"] = panel[column].notna().map(lambda ok: "direct_ndgain" if ok else pd.NA)
    for column in ["pdi", "idv", "mas", "uai", "lto", "ind"]:
        panel[f"src_{column}"] = panel[column].notna().map(lambda ok: "direct_hofstede" if ok else pd.NA)

    panel["model_region"] = panel.apply(guess_model_region, axis=1)
    panel["wgi_pv_unit"] = ((panel["wgi_pv"] + 2.5) / 5.0).clip(0.0, 1.0)
    panel["wgi_ge_unit"] = ((panel["wgi_ge"] + 2.5) / 5.0).clip(0.0, 1.0)
    panel["wgi_rl_unit"] = ((panel["wgi_rl"] + 2.5) / 5.0).clip(0.0, 1.0)
    panel["wgi_va_unit"] = ((panel["wgi_va"] + 2.5) / 5.0).clip(0.0, 1.0)

    overrides = load_overrides(data_root / "manual_country_overrides.csv")
    override_only = overrides[~overrides["iso3"].isin(panel["iso3"])].copy()
    if not override_only.empty:
        extra_rows = pd.DataFrame(
            {
                "iso3": override_only["iso3"],
                "iso2": pd.NA,
                "name": override_only["name"],
                "wb_region": override_only["model_region"],
                "income_level": "Override",
            }
        )
        panel = pd.concat([panel, extra_rows], ignore_index=True, sort=False)

    panel = apply_overrides(panel, overrides)

    panel["alliance_block"] = panel.apply(default_alliance, axis=1)
    panel["regime_type"] = panel.apply(default_regime, axis=1)
    panel = apply_overrides(panel, overrides)

    for column in ["gdp_usd_current", "population"]:
        fill_by_region(panel, column, strategy="median")
    for column in [
        "fx_reserves_usd",
        "public_debt_pct_gdp",
        "co2_mtco2e",
        "inequality_gini",
        "water_stress_pct",
        "military_gdp_ratio",
        "military_spending_usd",
        "wgi_pv",
        "wgi_ge",
        "wgi_rl",
        "wgi_va",
        "rd_pct_gdp",
        "high_tech_exports_pct",
        "manufacturing_share_pct",
        "energy_use_kg_oe_pc",
        "energy_imports_net_pct",
        "agri_share_pct",
        "food_production_index",
        "arable_land_pct",
        "climate_vulnerability",
        "habitat_vulnerability",
        "ecosystem_vulnerability",
        "ndgain_governance_readiness",
        "pdi",
        "idv",
        "mas",
        "uai",
        "lto",
        "ind",
    ]:
        fill_by_region(panel, column, strategy="median")

    for column in ["coal_rents_pct", "gas_rents_pct", "oil_rents_pct", "mineral_rents_pct"]:
        fill_by_region(panel, column, strategy="zero", default_value=0.0)

    panel["wgi_pv_unit"] = ((panel["wgi_pv"] + 2.5) / 5.0).clip(0.0, 1.0)
    panel["wgi_ge_unit"] = ((panel["wgi_ge"] + 2.5) / 5.0).clip(0.0, 1.0)
    panel["wgi_rl_unit"] = ((panel["wgi_rl"] + 2.5) / 5.0).clip(0.0, 1.0)
    panel["wgi_va_unit"] = ((panel["wgi_va"] + 2.5) / 5.0).clip(0.0, 1.0)

    panel["fossil_rents_pct"] = panel[["coal_rents_pct", "gas_rents_pct", "oil_rents_pct"]].sum(axis=1)
    panel["name"] = panel["name"].fillna(panel["ndgain_name"]).fillna(panel["hofstede_name"])
    panel = attach_resource_layer(panel, data_root)
    panel["gdp_per_capita"] = panel["gdp_usd_current"] / panel["population"]
    panel["fx_to_gdp"] = panel["fx_reserves_usd"] / panel["gdp_usd_current"]
    panel["water_stress"] = (panel["water_stress_pct"] / 100.0).clip(0.0, 1.0)
    panel["climate_risk"] = panel["climate_vulnerability"].clip(0.0, 1.0)
    panel["biodiversity_local"] = (
        1.0 - 0.5 * (panel["habitat_vulnerability"] + panel["ecosystem_vulnerability"])
    ).clip(0.0, 1.0)

    log_gdp_pc = panel["gdp_per_capita"].map(lambda value: math.log(max(value, 1.0)))
    log_mil_spend = panel["military_spending_usd"].map(lambda value: math.log(max(value, 1.0)))
    gdp_pc_norm = robust_minmax(log_gdp_pc)
    fx_gdp_norm = robust_minmax(panel["fx_to_gdp"])
    debt_norm = robust_minmax(panel["public_debt_pct_gdp"])
    gini_norm = (panel["inequality_gini"] / 100.0).clip(0.0, 1.0)
    rd_norm = robust_minmax(panel["rd_pct_gdp"])
    ht_norm = robust_minmax(panel["high_tech_exports_pct"])
    mil_spend_norm = robust_minmax(log_mil_spend)
    fossil_norm = robust_minmax(panel["fossil_rents_pct"])
    mineral_norm = robust_minmax(panel["mineral_rents_pct"])
    arable_norm = robust_minmax(panel["arable_land_pct"])
    food_index_norm = robust_minmax(panel["food_production_index"])

    panel["regime_stability"] = (
        0.55 * panel["wgi_pv_unit"] + 0.25 * panel["wgi_rl_unit"] + 0.20 * panel["wgi_ge_unit"]
    ).clip(0.0, 1.0)
    panel["trust_gov"] = (
        0.42 * panel["wgi_ge_unit"]
        + 0.23 * panel["wgi_va_unit"]
        + 0.20 * panel["regime_stability"]
        + 0.15 * (1.0 - gini_norm)
    ).clip(0.0, 1.0)
    panel["security_index"] = (
        0.45 * panel["wgi_rl_unit"] + 0.35 * panel["wgi_ge_unit"] + 0.20 * fx_gdp_norm
    ).clip(0.0, 1.0)
    panel["tech_level"] = (
        0.65 + 0.75 * gdp_pc_norm + 0.25 * rd_norm + 0.20 * ht_norm + 0.15 * panel["wgi_ge_unit"]
    ).clip(lower=0.5)
    panel["military_power"] = (
        0.50 + 0.90 * mil_spend_norm + 0.15 * panel["security_index"] + 0.10 * (panel["tech_level"] - 1.0)
    ).clip(lower=0.3)
    panel["debt_crisis_prone"] = (
        0.50 * debt_norm + 0.30 * (1.0 - fx_gdp_norm) + 0.20 * (1.0 - panel["regime_stability"])
    ).clip(0.0, 1.0)
    panel["social_tension"] = (
        0.35 * (1.0 - panel["trust_gov"])
        + 0.25 * gini_norm
        + 0.15 * panel["water_stress"]
        + 0.10 * panel["climate_risk"]
        + 0.15 * (1.0 - panel["regime_stability"])
    ).clip(0.0, 1.0)
    panel["conflict_proneness"] = (
        0.35 * (1.0 - panel["regime_stability"])
        + 0.25 * panel["social_tension"]
        + 0.20 * panel["climate_risk"]
        + 0.20 * robust_minmax(panel["military_gdp_ratio"])
    ).clip(0.0, 1.0)
    panel["traditional_secular"] = (
        2.0
        + 5.0 * gdp_pc_norm
        + 1.0 * (panel["idv"] / 100.0)
        - 1.0 * (panel["pdi"] / 100.0)
        + 0.7 * panel["wgi_va_unit"]
    ).clip(0.0, 10.0)
    panel["survival_self_expression"] = (
        2.0
        + 5.0 * panel["trust_gov"]
        + 1.5 * (panel["ind"] / 100.0)
        + 1.0 * (panel["idv"] / 100.0)
        - 1.0 * panel["social_tension"]
    ).clip(0.0, 10.0)
    return panel


def summarize_sources(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for column in columns:
        source_column = f"src_{column}"
        counts = frame[source_column].fillna("missing").value_counts().to_dict()
        for source_kind, count in counts.items():
            records.append({"field": column, "source_kind": source_kind, "count": int(count)})
    return pd.DataFrame.from_records(records).sort_values(["field", "count"], ascending=[True, False])


def build_actor_base(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    top50 = (
        panel[panel["gdp_usd_current"].notna()]
        .sort_values("gdp_usd_current", ascending=False)
        .head(50)[["iso3", "name", "gdp_usd_current", "model_region"]]
        .copy()
    )
    top_codes = set(top50["iso3"])
    top_codes.add("TWN")

    selected = panel[panel["iso3"].isin(top_codes)].copy()
    residual = panel[~panel["iso3"].isin(top_codes)].copy()
    residual = residual[residual["gdp_usd_current"].notna() & residual["population"].notna()].copy()

    residual_rows: list[pd.Series] = []
    for region, group in residual.groupby("model_region"):
        if group.empty:
            continue
        name, alliance_block, regime_type = RESIDUAL_DEFAULTS[region]
        aggregated = pd.Series(
            {
                "iso3": f"AG_{region.upper().replace(' ', '_')[:8]}",
                "name": name,
                "model_region": region,
                "alliance_block": alliance_block,
                "regime_type": regime_type,
                "wb_region": region,
                "income_level": "Aggregate",
                "gdp_usd_current": group["gdp_usd_current"].sum(),
                "population": group["population"].sum(),
                "fx_reserves_usd": group["fx_reserves_usd"].sum(),
                "co2_mtco2e": group["co2_mtco2e"].sum(),
                "military_spending_usd": group["military_spending_usd"].sum(),
                "public_debt_pct_gdp": weighted_average(group, "public_debt_pct_gdp", "gdp_usd_current"),
                "inequality_gini": weighted_average(group, "inequality_gini", "population"),
                "water_stress_pct": weighted_average(group, "water_stress_pct", "population"),
                "military_gdp_ratio": weighted_average(group, "military_gdp_ratio", "gdp_usd_current"),
                "wgi_pv": weighted_average(group, "wgi_pv", "population"),
                "wgi_ge": weighted_average(group, "wgi_ge", "population"),
                "wgi_rl": weighted_average(group, "wgi_rl", "population"),
                "wgi_va": weighted_average(group, "wgi_va", "population"),
                "rd_pct_gdp": weighted_average(group, "rd_pct_gdp", "gdp_usd_current"),
                "high_tech_exports_pct": weighted_average(group, "high_tech_exports_pct", "gdp_usd_current"),
                "manufacturing_share_pct": weighted_average(group, "manufacturing_share_pct", "gdp_usd_current"),
                "energy_use_kg_oe_pc": weighted_average(group, "energy_use_kg_oe_pc", "population"),
                "energy_imports_net_pct": weighted_average(group, "energy_imports_net_pct", "population"),
                "agri_share_pct": weighted_average(group, "agri_share_pct", "gdp_usd_current"),
                "food_production_index": weighted_average(group, "food_production_index", "population"),
                "arable_land_pct": weighted_average(group, "arable_land_pct", "population"),
                "coal_rents_pct": weighted_average(group, "coal_rents_pct", "gdp_usd_current"),
                "gas_rents_pct": weighted_average(group, "gas_rents_pct", "gdp_usd_current"),
                "oil_rents_pct": weighted_average(group, "oil_rents_pct", "gdp_usd_current"),
                "mineral_rents_pct": weighted_average(group, "mineral_rents_pct", "gdp_usd_current"),
                "climate_vulnerability": weighted_average(group, "climate_vulnerability", "population"),
                "habitat_vulnerability": weighted_average(group, "habitat_vulnerability", "population"),
                "ecosystem_vulnerability": weighted_average(group, "ecosystem_vulnerability", "population"),
                "ndgain_governance_readiness": weighted_average(
                    group, "ndgain_governance_readiness", "population"
                ),
                "pdi": weighted_average(group, "pdi", "population"),
                "idv": weighted_average(group, "idv", "population"),
                "mas": weighted_average(group, "mas", "population"),
                "uai": weighted_average(group, "uai", "population"),
                "lto": weighted_average(group, "lto", "population"),
                "ind": weighted_average(group, "ind", "population"),
                "energy_reserve_raw": group["energy_reserve_raw"].sum(),
                "energy_production_raw": group["energy_production_raw"].sum(),
                "energy_consumption_raw": group["energy_consumption_raw"].sum(),
                "food_reserve_raw": group["food_reserve_raw"].sum(),
                "food_production_raw": group["food_production_raw"].sum(),
                "food_consumption_raw": group["food_consumption_raw"].sum(),
                "metals_reserve_raw": group["metals_reserve_raw"].sum(),
                "metals_production_raw": group["metals_production_raw"].sum(),
                "metals_consumption_raw": group["metals_consumption_raw"].sum(),
            }
        )
        residual_rows.append(aggregated)

    residual_frame = pd.DataFrame(residual_rows)
    selected = pd.concat([selected, residual_frame], ignore_index=True, sort=False)
    return selected, top50


def scale_resource_layer(frame: pd.DataFrame) -> pd.DataFrame:
    scaled = frame.copy()

    energy_total = pd.to_numeric(scaled["energy_consumption_raw"], errors="coerce").clip(lower=0.0).sum()
    energy_factor = RESOURCE_WORLD_TOTALS["energy_consumption"] / energy_total if energy_total > 0 else 1.0
    scaled["energy_production"] = pd.to_numeric(scaled["energy_production_raw"], errors="coerce").fillna(0.0) * energy_factor
    scaled["energy_consumption"] = pd.to_numeric(scaled["energy_consumption_raw"], errors="coerce").fillna(0.0) * energy_factor
    scaled["energy_reserve"] = pd.to_numeric(scaled["energy_reserve_raw"], errors="coerce").fillna(0.0) * energy_factor

    food_total = pd.to_numeric(scaled["food_consumption_raw"], errors="coerce").clip(lower=0.0).sum()
    food_factor = RESOURCE_WORLD_TOTALS["food_consumption"] / food_total if food_total > 0 else 1.0
    scaled["food_production"] = pd.to_numeric(scaled["food_production_raw"], errors="coerce").fillna(0.0) * food_factor
    scaled["food_consumption"] = pd.to_numeric(scaled["food_consumption_raw"], errors="coerce").fillna(0.0) * food_factor
    scaled["food_reserve"] = pd.to_numeric(scaled["food_reserve_raw"], errors="coerce").fillna(0.0) * food_factor

    metals_prod_total = pd.to_numeric(scaled["metals_production_raw"], errors="coerce").clip(lower=0.0).sum()
    metals_prod_factor = (
        RESOURCE_WORLD_TOTALS["metals_production"] / metals_prod_total if metals_prod_total > 0 else 1.0
    )
    metals_cons_total = pd.to_numeric(scaled["metals_consumption_raw"], errors="coerce").clip(lower=0.0).sum()
    metals_cons_factor = (
        RESOURCE_WORLD_TOTALS["metals_consumption"] / metals_cons_total if metals_cons_total > 0 else 1.0
    )
    scaled["metals_production"] = pd.to_numeric(scaled["metals_production_raw"], errors="coerce").fillna(0.0) * metals_prod_factor
    scaled["metals_consumption"] = pd.to_numeric(scaled["metals_consumption_raw"], errors="coerce").fillna(0.0) * metals_cons_factor
    scaled["metals_reserve"] = pd.to_numeric(scaled["metals_reserve_raw"], errors="coerce").fillna(0.0) * metals_prod_factor

    return scaled


def recompute_final_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame = scale_resource_layer(frame)
    frame["wgi_pv_unit"] = ((frame["wgi_pv"] + 2.5) / 5.0).clip(0.0, 1.0)
    frame["wgi_ge_unit"] = ((frame["wgi_ge"] + 2.5) / 5.0).clip(0.0, 1.0)
    frame["wgi_rl_unit"] = ((frame["wgi_rl"] + 2.5) / 5.0).clip(0.0, 1.0)
    frame["wgi_va_unit"] = ((frame["wgi_va"] + 2.5) / 5.0).clip(0.0, 1.0)
    frame["fossil_rents_pct"] = frame[["coal_rents_pct", "gas_rents_pct", "oil_rents_pct"]].sum(axis=1)
    frame["gdp_per_capita"] = frame["gdp_usd_current"] / frame["population"]
    frame["fx_to_gdp"] = frame["fx_reserves_usd"] / frame["gdp_usd_current"]
    frame["water_stress"] = (frame["water_stress_pct"] / 100.0).clip(0.0, 1.0)
    frame["climate_risk"] = frame["climate_vulnerability"].clip(0.0, 1.0)
    frame["biodiversity_local"] = (
        1.0 - 0.5 * (frame["habitat_vulnerability"] + frame["ecosystem_vulnerability"])
    ).clip(0.0, 1.0)

    log_gdp_pc = frame["gdp_per_capita"].map(lambda value: math.log(max(value, 1.0)))
    log_mil_spend = frame["military_spending_usd"].map(lambda value: math.log(max(value, 1.0)))
    gdp_pc_norm = robust_minmax(log_gdp_pc)
    fx_gdp_norm = robust_minmax(frame["fx_to_gdp"])
    debt_norm = robust_minmax(frame["public_debt_pct_gdp"])
    gini_norm = (frame["inequality_gini"] / 100.0).clip(0.0, 1.0)
    rd_norm = robust_minmax(frame["rd_pct_gdp"])
    ht_norm = robust_minmax(frame["high_tech_exports_pct"])
    mil_spend_norm = robust_minmax(log_mil_spend)

    frame["regime_stability"] = (
        0.55 * frame["wgi_pv_unit"] + 0.25 * frame["wgi_rl_unit"] + 0.20 * frame["wgi_ge_unit"]
    ).clip(0.0, 1.0)
    frame["trust_gov"] = (
        0.42 * frame["wgi_ge_unit"]
        + 0.23 * frame["wgi_va_unit"]
        + 0.20 * frame["regime_stability"]
        + 0.15 * (1.0 - gini_norm)
    ).clip(0.0, 1.0)
    frame["security_index"] = (
        0.45 * frame["wgi_rl_unit"] + 0.35 * frame["wgi_ge_unit"] + 0.20 * fx_gdp_norm
    ).clip(0.0, 1.0)
    frame["tech_level"] = (
        0.65 + 0.75 * gdp_pc_norm + 0.25 * rd_norm + 0.20 * ht_norm + 0.15 * frame["wgi_ge_unit"]
    ).clip(lower=0.5)
    frame["military_power"] = (
        0.50 + 0.90 * mil_spend_norm + 0.15 * frame["security_index"] + 0.10 * (frame["tech_level"] - 1.0)
    ).clip(lower=0.3)
    frame["debt_crisis_prone"] = (
        0.50 * debt_norm + 0.30 * (1.0 - fx_gdp_norm) + 0.20 * (1.0 - frame["regime_stability"])
    ).clip(0.0, 1.0)
    frame["social_tension"] = (
        0.35 * (1.0 - frame["trust_gov"])
        + 0.25 * gini_norm
        + 0.15 * frame["water_stress"]
        + 0.10 * frame["climate_risk"]
        + 0.15 * (1.0 - frame["regime_stability"])
    ).clip(0.0, 1.0)
    frame["conflict_proneness"] = (
        0.35 * (1.0 - frame["regime_stability"])
        + 0.25 * frame["social_tension"]
        + 0.20 * frame["climate_risk"]
        + 0.20 * robust_minmax(frame["military_gdp_ratio"])
    ).clip(0.0, 1.0)
    frame["traditional_secular"] = (
        2.0
        + 5.0 * gdp_pc_norm
        + 1.0 * (frame["idv"] / 100.0)
        - 1.0 * (frame["pdi"] / 100.0)
        + 0.7 * frame["wgi_va_unit"]
    ).clip(0.0, 10.0)
    frame["survival_self_expression"] = (
        2.0
        + 5.0 * frame["trust_gov"]
        + 1.5 * (frame["ind"] / 100.0)
        + 1.0 * (frame["idv"] / 100.0)
        - 1.0 * frame["social_tension"]
    ).clip(0.0, 10.0)
    frame["gdp"] = frame["gdp_usd_current"] / 1e12
    frame["fx_reserves"] = frame["fx_reserves_usd"] / 1e12
    frame["co2_annual_emissions"] = frame["co2_mtco2e"] / 1000.0
    frame["region"] = frame["model_region"]
    frame["id"] = frame["iso3"]
    return frame


def build_output(frame: pd.DataFrame) -> pd.DataFrame:
    compiled = recompute_final_metrics(frame)
    compiled = compiled.sort_values(["gdp_usd_current", "name"], ascending=[False, True]).reset_index(drop=True)
    for column in OUTPUT_COLUMNS:
        if column not in compiled.columns:
            compiled[column] = 0.0
    return compiled[OUTPUT_COLUMNS[:5] + OUTPUT_COLUMNS[5:]]


def build_imputed_panel_view(panel: pd.DataFrame) -> pd.DataFrame:
    panel = scale_resource_layer(panel)
    base_columns = ["iso3", "name", "wb_region", "income_level", "model_region", "alliance_block", "regime_type"]
    source_columns = IMPUTED_SOURCE_COLUMNS + [f"src_{column}" for column in IMPUTED_SOURCE_COLUMNS]
    columns = base_columns + source_columns + IMPUTED_DERIVED_COLUMNS
    view = panel[columns].copy()
    view["wb_region"] = view["wb_region"].fillna(view["model_region"])
    view["income_level"] = view["income_level"].fillna("Unknown")
    return view


def build_actor_source_audit(panel: pd.DataFrame, actor_ids: set[str]) -> pd.DataFrame:
    audit_columns = [
        "iso3",
        "name",
        "model_region",
        "alliance_block",
        "regime_type",
        *[f"src_{column}" for column in IMPUTED_SOURCE_COLUMNS],
    ]
    audit = panel[panel["iso3"].isin(actor_ids)][audit_columns].copy()
    return audit.sort_values(["model_region", "name"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the operational agent state CSV from external source layers."
    )
    parser.add_argument("--target-year", type=int, default=TARGET_YEAR)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(
            "/Users/theclimateguy/Documents/jupyter_lab/GIM15/data/agent_states_operational.csv"
        ),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("/Users/theclimateguy/Documents/jupyter_lab/GIM15/data/agent_state_pipeline"),
    )
    args = parser.parse_args()

    generated_dir = args.data_root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    panel = build_country_panel(args.data_root)
    panel.to_csv(generated_dir / "country_panel_raw.csv", index=False)
    imputed_panel = build_imputed_panel_view(panel)
    if imputed_panel.isna().any().any():
        raise ValueError("country_panel_imputed.csv still contains missing values")
    imputed_panel.to_csv(generated_dir / "country_panel_imputed.csv", index=False)

    coverage = summarize_sources(
        panel,
        [
            "gdp_usd_current",
            "population",
            "fx_reserves_usd",
            "public_debt_pct_gdp",
            "co2_mtco2e",
            "inequality_gini",
            "water_stress_pct",
            "military_gdp_ratio",
            "military_spending_usd",
            "energy_imports_net_pct",
            "pdi",
            "idv",
            "mas",
            "uai",
            "lto",
            "ind",
            "energy_production_raw",
            "energy_consumption_raw",
            "energy_reserve_raw",
            "food_production_raw",
            "food_consumption_raw",
            "food_reserve_raw",
            "metals_production_raw",
            "metals_consumption_raw",
            "metals_reserve_raw",
        ],
    )
    coverage.to_csv(generated_dir / "coverage_summary.csv", index=False)

    actor_base, top50 = build_actor_base(panel)
    actor_base.to_csv(generated_dir / "actor_base_inputs.csv", index=False)
    top50.to_csv(generated_dir / "top50_2023_gdp.csv", index=False)
    actor_ids = set(top50["iso3"])
    actor_audit = build_actor_source_audit(panel, actor_ids)
    actor_audit.to_csv(generated_dir / "top50_source_audit.csv", index=False)

    compiled = build_output(actor_base)
    compiled.to_csv(args.output_csv, index=False)


if __name__ == "__main__":
    main()
