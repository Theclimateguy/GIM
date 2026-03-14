from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from .runtime import REPO_ROOT

from .core import calibration_params as cal
from .core.core import GTCO2_PER_PPM, WorldState
from .core.policy import make_policy_map
from .core.simulation import step_world
from .core.world_factory import make_world_from_csv


FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
DEFAULT_OBSERVED_FIXTURE = FIXTURES_DIR / "historical_backtest_observed.json"
DEFAULT_INITIAL_STATE_CSV = FIXTURES_DIR / "historical_backtest_state_2015.csv"
DEFAULT_BASELINE_FIXTURE = FIXTURES_DIR / "historical_backtest_baseline.json"
DEFAULT_POLICY_MODE = "simple"

# Structural validation is anchored on the legacy 20-country surface because it has
# one sovereign row per GDP target plus an explicit Rest-of-World residual actor.
GDP_BACKTEST_ACTORS = (
    "United States",
    "China",
    "Japan",
    "Germany",
    "India",
    "United Kingdom",
    "France",
    "Italy",
    "Brazil",
    "Canada",
    "South Korea",
    "Russia",
    "Australia",
    "Spain",
    "Mexico",
    "Indonesia",
    "Netherlands",
    "Saudi Arabia",
    "Turkey",
    "Switzerland",
)


@dataclass(frozen=True)
class HistoricalBacktestResult:
    start_year: int
    end_year: int
    policy_mode: str
    enable_extreme_events: bool
    state_csv: str
    observed_fixture: str
    gdp_rmse_trillions: float
    global_co2_rmse_gtco2: float
    temperature_rmse_c: float
    country_gdp_rmse_trillions: dict[str, float]
    predicted_gdp_trillions: dict[int, dict[str, float]]
    actual_gdp_trillions: dict[int, dict[str, float]]
    predicted_global_co2_gtco2: dict[int, float]
    actual_global_co2_gtco2: dict[int, float]
    predicted_temperature_c: dict[int, float]
    actual_temperature_c: dict[int, float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _coerce_int_keyed_series(raw: dict[str, float] | dict[int, float]) -> dict[int, float]:
    return {int(key): float(value) for key, value in raw.items()}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_observed_fixture(path: Path = DEFAULT_OBSERVED_FIXTURE) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_historical_backtest_baseline(
    path: Path = DEFAULT_BASELINE_FIXTURE,
) -> HistoricalBacktestResult:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return HistoricalBacktestResult(
        start_year=int(raw["start_year"]),
        end_year=int(raw["end_year"]),
        policy_mode=str(raw["policy_mode"]),
        enable_extreme_events=bool(raw["enable_extreme_events"]),
        state_csv=str(raw["state_csv"]),
        observed_fixture=str(raw["observed_fixture"]),
        gdp_rmse_trillions=float(raw["gdp_rmse_trillions"]),
        global_co2_rmse_gtco2=float(raw["global_co2_rmse_gtco2"]),
        temperature_rmse_c=float(raw["temperature_rmse_c"]),
        country_gdp_rmse_trillions={
            str(key): float(value) for key, value in raw["country_gdp_rmse_trillions"].items()
        },
        predicted_gdp_trillions={
            int(year): {str(name): float(value) for name, value in values.items()}
            for year, values in raw["predicted_gdp_trillions"].items()
        },
        actual_gdp_trillions={
            int(year): {str(name): float(value) for name, value in values.items()}
            for year, values in raw["actual_gdp_trillions"].items()
        },
        predicted_global_co2_gtco2=_coerce_int_keyed_series(raw["predicted_global_co2_gtco2"]),
        actual_global_co2_gtco2=_coerce_int_keyed_series(raw["actual_global_co2_gtco2"]),
        predicted_temperature_c=_coerce_int_keyed_series(raw["predicted_temperature_c"]),
        actual_temperature_c=_coerce_int_keyed_series(raw["actual_temperature_c"]),
    )


def _rmse(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    mse = sum((predicted - actual) ** 2 for predicted, actual in pairs) / len(pairs)
    return math.sqrt(mse)


def _seed_historical_globals(world: WorldState, observed: dict[str, object], start_year: int) -> None:
    atmospheric_co2_ppm = _coerce_int_keyed_series(observed["atmospheric_co2_ppm"])
    temperature_c = _coerce_int_keyed_series(observed["temperature_c_preindustrial"])
    world.global_state.co2 = atmospheric_co2_ppm[start_year] * GTCO2_PER_PPM
    world.global_state.temperature_global = temperature_c[start_year]
    world.global_state.temperature_ocean = temperature_c[start_year] - 0.4
    world.global_state.carbon_pools = []
    world.global_state._calendar_year_base = start_year


class _temporary_decarb_rate:
    def __init__(self, value: float | None):
        self._value = value
        self._original_structural = cal.DECARB_RATE_STRUCTURAL
        self._original_alias = cal.DECARB_RATE

    def __enter__(self) -> None:
        if self._value is not None:
            override = float(self._value)
            cal.DECARB_RATE_STRUCTURAL = override
            cal.DECARB_RATE = override
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        cal.DECARB_RATE_STRUCTURAL = self._original_structural
        cal.DECARB_RATE = self._original_alias


def run_historical_backtest(
    *,
    state_csv: str | Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    policy_mode: str = DEFAULT_POLICY_MODE,
    enable_extreme_events: bool = False,
    decarb_rate_override: float | None = None,
) -> HistoricalBacktestResult:
    state_csv_path = Path(state_csv)
    observed_path = Path(observed_fixture)
    observed = _load_observed_fixture(observed_path)

    start_year = int(observed["start_year"])
    end_year = int(observed["end_year"])
    if end_year < start_year:
        raise ValueError(f"Invalid backtest range: {start_year}..{end_year}")

    actual_gdp_trillions = {
        year: {name: float(value) for name, value in values.items()}
        for year, values in (
            (int(year_key), year_values)
            for year_key, year_values in observed["gdp_trillions_by_year"].items()
        )
    }
    actual_global_co2_gtco2 = _coerce_int_keyed_series(observed["global_co2_gtco2"])
    actual_temperature_c = _coerce_int_keyed_series(observed["temperature_c_preindustrial"])

    with _temporary_decarb_rate(decarb_rate_override):
        world = make_world_from_csv(str(state_csv_path))
        _seed_historical_globals(world, observed, start_year)

        policies = make_policy_map(world.agents.keys(), mode=policy_mode)

        predicted_gdp_trillions: dict[int, dict[str, float]] = {
            start_year: {
                agent.name: agent.economy.gdp
                for agent in world.agents.values()
                if agent.name in GDP_BACKTEST_ACTORS
            }
        }
        predicted_global_co2_gtco2 = {
            start_year: sum(agent.climate.co2_annual_emissions for agent in world.agents.values())
        }
        predicted_temperature_c = {start_year: world.global_state.temperature_global}

        for offset in range(1, end_year - start_year + 1):
            year = start_year + offset
            world = step_world(world, policies, enable_extreme_events=enable_extreme_events)
            predicted_gdp_trillions[year] = {
                agent.name: agent.economy.gdp
                for agent in world.agents.values()
                if agent.name in GDP_BACKTEST_ACTORS
            }
            predicted_global_co2_gtco2[year] = sum(
                agent.climate.co2_annual_emissions for agent in world.agents.values()
            )
            predicted_temperature_c[year] = world.global_state.temperature_global

    gdp_pairs = [
        (predicted_gdp_trillions[year][country], actual_gdp_trillions[year][country])
        for year in range(start_year, end_year + 1)
        for country in GDP_BACKTEST_ACTORS
    ]
    country_gdp_rmse_trillions = {
        country: _rmse(
            [
                (predicted_gdp_trillions[year][country], actual_gdp_trillions[year][country])
                for year in range(start_year, end_year + 1)
            ]
        )
        for country in GDP_BACKTEST_ACTORS
    }
    co2_pairs = [
        (predicted_global_co2_gtco2[year], actual_global_co2_gtco2[year])
        for year in range(start_year, end_year + 1)
    ]
    temperature_pairs = [
        (predicted_temperature_c[year], actual_temperature_c[year])
        for year in range(start_year, end_year + 1)
    ]

    return HistoricalBacktestResult(
        start_year=start_year,
        end_year=end_year,
        policy_mode=policy_mode,
        enable_extreme_events=enable_extreme_events,
        state_csv=_display_path(state_csv_path),
        observed_fixture=_display_path(observed_path),
        gdp_rmse_trillions=_rmse(gdp_pairs),
        global_co2_rmse_gtco2=_rmse(co2_pairs),
        temperature_rmse_c=_rmse(temperature_pairs),
        country_gdp_rmse_trillions=country_gdp_rmse_trillions,
        predicted_gdp_trillions=predicted_gdp_trillions,
        actual_gdp_trillions=actual_gdp_trillions,
        predicted_global_co2_gtco2=predicted_global_co2_gtco2,
        actual_global_co2_gtco2=actual_global_co2_gtco2,
        predicted_temperature_c=predicted_temperature_c,
        actual_temperature_c=actual_temperature_c,
    )


def format_historical_backtest_result(result: HistoricalBacktestResult, top_n: int = 5) -> str:
    worst_countries = sorted(
        result.country_gdp_rmse_trillions.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:top_n]
    lines = [
        f"Historical backtest {result.start_year}-{result.end_year}",
        f"GDP RMSE (20-country, trillions USD): {result.gdp_rmse_trillions:.3f}",
        f"Global CO2 RMSE (GtCO2): {result.global_co2_rmse_gtco2:.3f}",
        f"Temperature RMSE (deg C): {result.temperature_rmse_c:.3f}",
        "Worst GDP RMSE actors: "
        + ", ".join(f"{name}={value:.3f}" for name, value in worst_countries),
    ]
    return "\n".join(lines)


__all__ = [
    "DEFAULT_BASELINE_FIXTURE",
    "DEFAULT_INITIAL_STATE_CSV",
    "DEFAULT_OBSERVED_FIXTURE",
    "GDP_BACKTEST_ACTORS",
    "HistoricalBacktestResult",
    "format_historical_backtest_result",
    "load_historical_backtest_baseline",
    "run_historical_backtest",
]
