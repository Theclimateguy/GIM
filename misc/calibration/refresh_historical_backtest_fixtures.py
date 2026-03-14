from __future__ import annotations

import csv
import json
from io import BytesIO
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
BASE_STATE_CSV = REPO_ROOT / "data" / "agent_states.csv"
OBSERVED_OUTPUT = FIXTURES_DIR / "historical_backtest_observed.json"
STATE_OUTPUT = FIXTURES_DIR / "historical_backtest_state_2015.csv"
CALIBRATION_DIR = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(CALIBRATION_DIR) not in sys.path:
    sys.path.insert(0, str(CALIBRATION_DIR))

from gim.core.state_artifact import compute_emissions_scale_from_state_csv  # noqa: E402
from refresh_state_artifact_manifest import (  # noqa: E402
    DEFAULT_BUILDER_REFERENCE,
    DEFAULT_HANDOFF_CONTRACT,
    DEFAULT_STATE_CSV,
    build_manifest,
)

START_YEAR = 2015
END_YEAR = 2023

WORLD_BANK_BASE = "https://api.worldbank.org/v2"
HADCRUT_URL = (
    "https://hadleyserver.metoffice.gov.uk/hadobs/hadcrut5/data/HadCRUT.5.1.0.0/"
    "analysis/diagnostics/HadCRUT.5.1.0.0.analysis.summary_series.global.annual.csv"
)
NOAA_CO2_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_gl.txt"
GCP_BUDGET_URL = "https://globalcarbonbudget.org/download/1725/?tmstv=1746005505"

COUNTRIES = {
    "C01": ("USA", "United States"),
    "C02": ("CHN", "China"),
    "C03": ("JPN", "Japan"),
    "C04": ("DEU", "Germany"),
    "C05": ("IND", "India"),
    "C06": ("GBR", "United Kingdom"),
    "C07": ("FRA", "France"),
    "C08": ("ITA", "Italy"),
    "C09": ("BRA", "Brazil"),
    "C10": ("CAN", "Canada"),
    "C11": ("KOR", "South Korea"),
    "C12": ("RUS", "Russia"),
    "C13": ("AUS", "Australia"),
    "C14": ("ESP", "Spain"),
    "C15": ("MEX", "Mexico"),
    "C16": ("IDN", "Indonesia"),
    "C17": ("NLD", "Netherlands"),
    "C18": ("SAU", "Saudi Arabia"),
    "C19": ("TUR", "Turkey"),
    "C20": ("CHE", "Switzerland"),
}

WB_INDICATORS = {
    "gdp_usd": "NY.GDP.MKTP.CD",
    "population": "SP.POP.TOTL",
    "fx_reserves_usd": "FI.RES.XGLD.CD",
    "public_debt_pct_gdp": "GC.DOD.TOTL.GD.ZS",
    "co2_mt": "EN.GHG.CO2.MT.CE.AR5",
}

SOURCE_NOTES = {
    "wdi_gdp": (
        "World Bank WDI API, indicator NY.GDP.MKTP.CD, annual current USD for the 20-country "
        "legacy backtest surface."
    ),
    "wdi_population": "World Bank WDI API, indicator SP.POP.TOTL, used for 2015 initial-state alignment.",
    "wdi_fx_reserves": "World Bank WDI API, indicator FI.RES.XGLD.CD, used for 2015 initial-state alignment.",
    "wdi_public_debt": "World Bank WDI API, indicator GC.DOD.TOTL.GD.ZS, used for 2015 initial-state alignment.",
    "wdi_country_co2": "World Bank WDI API, indicator EN.GHG.CO2.MT.CE.AR5, used for 2015 initial-state alignment.",
    "gcp_global_co2": (
        "Global Carbon Budget 2024 workbook, sheet 'Global Carbon Budget', column "
        "'fossil emissions excluding carbonation', converted from GtC/yr to GtCO2/yr."
    ),
    "hadcrut5_temperature": (
        "HadCRUT.5.1.0.0 annual global summary series from the Met Office, rebased to an "
        "1850-1900 mean so the anomaly matches the model's preindustrial framing."
    ),
    "noaa_atmospheric_co2": (
        "NOAA GML global annual mean atmospheric CO2 concentration, used to seed the 2015 "
        "atmospheric stock before the simulation starts."
    ),
}


def _fetch_json(url: str) -> list[object]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def _fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _fetch_world_bank_indicator(indicator: str, start_year: int = 2010, end_year: int = END_YEAR) -> dict[str, dict[int, float]]:
    codes = ";".join([iso for iso, _name in COUNTRIES.values()] + ["WLD"])
    url = (
        f"{WORLD_BANK_BASE}/country/{codes}/indicator/{indicator}"
        f"?format=json&per_page=20000&date={start_year}:{end_year}"
    )
    payload = _fetch_json(url)
    out: dict[str, dict[int, float]] = {}
    for row in payload[1] or []:
        iso = row.get("countryiso3code")
        value = row.get("value")
        if value is None or not iso or iso == "NA":
            continue
        out.setdefault(str(iso), {})[int(row["date"])] = float(value)
    return out


def _latest_at_or_before(series: dict[int, float], target_year: int) -> float:
    eligible_years = [year for year in series if year <= target_year]
    if not eligible_years:
        raise KeyError(f"No series value available at or before {target_year}")
    return float(series[max(eligible_years)])


def _optional_latest_at_or_before(series: dict[int, float] | None, target_year: int) -> float | None:
    if not series:
        return None
    eligible_years = [year for year in series if year <= target_year]
    if not eligible_years:
        return None
    return float(series[max(eligible_years)])


def _load_hadcrut_preindustrial() -> dict[int, float]:
    rows = list(csv.DictReader(_fetch_text(HADCRUT_URL).splitlines()))
    anomalies = {int(row["Time"]): float(row["Anomaly (deg C)"]) for row in rows}
    preindustrial_mean = sum(anomalies[year] for year in range(1850, 1901)) / 51.0
    return {year: anomalies[year] - preindustrial_mean for year in range(START_YEAR, END_YEAR + 1)}


def _load_noaa_atmospheric_co2() -> dict[int, float]:
    out: dict[int, float] = {}
    for line in _fetch_text(NOAA_CO2_URL).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        out[int(parts[0])] = float(parts[1])
    return {year: out[year] for year in range(START_YEAR, END_YEAR + 1)}


def _load_global_carbon_budget_fossil_co2() -> dict[int, float]:
    payload = _fetch_bytes(GCP_BUDGET_URL)
    with ZipFile(BytesIO(payload)) as archive:
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", ns):
                shared_strings.append(
                    "".join(
                        text.text or ""
                        for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    )
                )

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
        fossil_emissions_gtco2: dict[int, float] = {}
        for row in sheet.findall("a:sheetData/a:row", ns):
            cells: dict[str, str] = {}
            for cell in row.findall("a:c", ns):
                ref = cell.attrib.get("r", "")
                column = "".join(ch for ch in ref if ch.isalpha())
                value_node = cell.find("a:v", ns)
                if value_node is None:
                    continue
                value = value_node.text or ""
                if cell.attrib.get("t") == "s":
                    value = shared_strings[int(value)]
                cells[column] = value
            if cells.get("A", "").isdigit() and "B" in cells:
                year = int(cells["A"])
                if START_YEAR <= year <= END_YEAR:
                    fossil_emissions_gtco2[year] = float(cells["B"]) * 3.664
    return fossil_emissions_gtco2


def _load_base_state_rows() -> tuple[list[str], list[dict[str, str]]]:
    with BASE_STATE_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _build_observed_fixture() -> tuple[dict[str, object], dict[str, dict[str, dict[int, float]]]]:
    indicators = {name: _fetch_world_bank_indicator(code) for name, code in WB_INDICATORS.items()}
    gdp_trillions_by_year = {
        year: {
            country_name: indicators["gdp_usd"][iso][year] / 1e12
            for iso, country_name in COUNTRIES.values()
        }
        for year in range(START_YEAR, END_YEAR + 1)
    }
    observed = {
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "gdp_trillions_by_year": gdp_trillions_by_year,
        "global_co2_gtco2": _load_global_carbon_budget_fossil_co2(),
        "temperature_c_preindustrial": _load_hadcrut_preindustrial(),
        "atmospheric_co2_ppm": _load_noaa_atmospheric_co2(),
        "source_notes": SOURCE_NOTES,
    }
    return observed, indicators


def _build_initial_state_csv(
    indicators: dict[str, dict[str, dict[int, float]]],
    *,
    output_path: Path,
) -> None:
    fieldnames, rows = _load_base_state_rows()
    world_gdp_2015 = indicators["gdp_usd"]["WLD"][START_YEAR]
    world_population_2015 = indicators["population"]["WLD"][START_YEAR]
    world_co2_2015 = indicators["co2_mt"]["WLD"][START_YEAR]

    top20_gdp_2015 = 0.0
    top20_population_2015 = 0.0
    top20_co2_2015 = 0.0
    for iso, _country_name in COUNTRIES.values():
        top20_gdp_2015 += indicators["gdp_usd"][iso][START_YEAR]
        top20_population_2015 += indicators["population"][iso][START_YEAR]
        top20_co2_2015 += indicators["co2_mt"][iso][START_YEAR]

    rest_of_world_row = next(row for row in rows if row["id"] == "C99")
    rest_of_world_gdp_2023 = float(rest_of_world_row["gdp"]) * 1e12

    updated_rows: list[dict[str, str]] = []
    for row in rows:
        updated = dict(row)
        if updated["id"] in COUNTRIES:
            iso, _country_name = COUNTRIES[updated["id"]]
            gdp_2015 = indicators["gdp_usd"][iso][START_YEAR]
            population_2015 = indicators["population"][iso][START_YEAR]
            fx_reserves_2015 = _optional_latest_at_or_before(
                indicators["fx_reserves_usd"].get(iso),
                START_YEAR,
            )
            if fx_reserves_2015 is None:
                fx_reserves_2015 = float(updated["fx_reserves"]) * 1e12
            debt_ratio_2015 = _optional_latest_at_or_before(
                indicators["public_debt_pct_gdp"].get(iso),
                START_YEAR,
            )
            if debt_ratio_2015 is None:
                debt_ratio_2015 = float(updated["public_debt"]) / max(float(updated["gdp"]), 1e-9) * 100.0
            co2_2015 = indicators["co2_mt"][iso][START_YEAR]

            gdp_ratio = gdp_2015 / max(float(updated["gdp"]) * 1e12, 1e-9)
            updated["gdp"] = f"{gdp_2015 / 1e12:.15g}"
            updated["capital"] = f"{float(updated['capital']) * gdp_ratio:.15g}"
            updated["population"] = f"{population_2015:.15g}"
            updated["public_debt"] = f"{(gdp_2015 * debt_ratio_2015 / 100.0) / 1e12:.15g}"
            updated["fx_reserves"] = f"{fx_reserves_2015 / 1e12:.15g}"
            updated["co2_annual_emissions"] = f"{co2_2015 / 1000.0:.15g}"
        elif updated["id"] == "C99":
            rest_gdp_2015 = max(world_gdp_2015 - top20_gdp_2015, 1e9)
            rest_population_2015 = max(world_population_2015 - top20_population_2015, 1.0)
            rest_co2_2015 = max(world_co2_2015 - top20_co2_2015, 0.0)
            gdp_ratio = rest_gdp_2015 / max(rest_of_world_gdp_2023, 1e-9)
            updated["gdp"] = f"{rest_gdp_2015 / 1e12:.15g}"
            updated["capital"] = f"{float(updated['capital']) * gdp_ratio:.15g}"
            updated["population"] = f"{rest_population_2015:.15g}"
            updated["public_debt"] = f"{float(updated['public_debt']) * gdp_ratio:.15g}"
            updated["fx_reserves"] = f"{float(updated['fx_reserves']) * gdp_ratio:.15g}"
            updated["co2_annual_emissions"] = f"{rest_co2_2015 / 1000.0:.15g}"
        updated_rows.append(updated)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)


def compute_emissions_scale(state_2015_path: str | Path, gcp_observed_2015: float) -> float:
    return compute_emissions_scale_from_state_csv(state_2015_path, gcp_observed_2015)


def _refresh_primary_artifact_manifest(
    *,
    state_2015_path: Path,
    observed: dict[str, object],
) -> Path:
    observed_global_co2_series = observed["global_co2_gtco2"]
    if START_YEAR in observed_global_co2_series:
        observed_global_co2 = float(observed_global_co2_series[START_YEAR])
    else:
        observed_global_co2 = float(observed_global_co2_series[str(START_YEAR)])
    emissions_scale = compute_emissions_scale(state_2015_path, observed_global_co2)
    manifest_path = DEFAULT_STATE_CSV.with_suffix(".artifacts.json")
    manifest = build_manifest(
        state_csv=DEFAULT_STATE_CSV,
        manifest_path=manifest_path,
        emissions_scale=emissions_scale,
        decarb_rate=0.049,
        target_year=2023,
        builder_reference=DEFAULT_BUILDER_REFERENCE,
        handoff_contract=DEFAULT_HANDOFF_CONTRACT,
        rebuild_source="data",
        emissions_reference_year=START_YEAR,
        emissions_reference_gtco2=observed_global_co2,
        emissions_reference_state_csv=state_2015_path,
        decarb_source="legacy",
        decarb_reference_rate=0.049,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    observed, indicators = _build_observed_fixture()
    OBSERVED_OUTPUT.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    _build_initial_state_csv(indicators, output_path=STATE_OUTPUT)
    manifest_path = _refresh_primary_artifact_manifest(state_2015_path=STATE_OUTPUT, observed=observed)
    print(OBSERVED_OUTPUT)
    print(STATE_OUTPUT)
    print(manifest_path)


if __name__ == "__main__":
    main()
