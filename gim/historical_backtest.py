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
    temperature_ensemble_size: int
    temperature_seed_base: int
    temperature_variability_sigma: float
    gdp_rmse_trillions: float
    global_co2_rmse_gtco2: float
    temperature_rmse_c: float
    temperature_bias_c: float
    temperature_predicted_std_c: float
    temperature_observed_std_c: float
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


def load_historical_observed_fixture(
    path: Path = DEFAULT_OBSERVED_FIXTURE,
) -> dict[str, object]:
    return _load_observed_fixture(path)


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
        temperature_ensemble_size=int(raw.get("temperature_ensemble_size", 1)),
        temperature_seed_base=int(raw.get("temperature_seed_base", 0)),
        temperature_variability_sigma=float(raw.get("temperature_variability_sigma", 0.0)),
        gdp_rmse_trillions=float(raw["gdp_rmse_trillions"]),
        global_co2_rmse_gtco2=float(raw["global_co2_rmse_gtco2"]),
        temperature_rmse_c=float(raw["temperature_rmse_c"]),
        temperature_bias_c=float(raw.get("temperature_bias_c", 0.0)),
        temperature_predicted_std_c=float(raw.get("temperature_predicted_std_c", 0.0)),
        temperature_observed_std_c=float(raw.get("temperature_observed_std_c", 0.0)),
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


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def compute_observed_global_co2_intensity(
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
) -> dict[int, float]:
    observed = _load_observed_fixture(Path(observed_fixture))
    start_year = int(observed["start_year"])
    end_year = int(observed["end_year"])
    co2 = _coerce_int_keyed_series(observed["global_co2_gtco2"])
    gdp = {
        int(year): sum(float(value) for value in values.values())
        for year, values in observed["gdp_trillions_by_year"].items()
    }
    return {
        year: co2[year] / max(gdp[year], 1e-9)
        for year in range(start_year, end_year + 1)
    }


def estimate_observed_decarb_rate(
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    *,
    method: str = "mean_pairwise",
) -> float:
    observed = _load_observed_fixture(Path(observed_fixture))
    start_year = int(observed["start_year"])
    end_year = int(observed["end_year"])
    intensity = compute_observed_global_co2_intensity(observed_fixture)

    if method == "end_to_end":
        return float(
            -math.log(intensity[end_year] / intensity[start_year]) / max(end_year - start_year, 1)
        )
    if method != "mean_pairwise":
        raise ValueError(f"Unsupported observed decarb estimation method: {method}")

    pairwise = [
        -math.log(intensity[year] / intensity[start_year]) / max(year - start_year, 1)
        for year in range(start_year + 1, end_year + 1)
    ]
    return float(sum(pairwise) / len(pairwise))


def _seed_historical_globals(world: WorldState, observed: dict[str, object], start_year: int) -> None:
    atmospheric_co2_ppm = _coerce_int_keyed_series(observed["atmospheric_co2_ppm"])
    temperature_c = _coerce_int_keyed_series(observed["temperature_c_preindustrial"])
    world.global_state.co2 = atmospheric_co2_ppm[start_year] * GTCO2_PER_PPM
    world.global_state.temperature_global = temperature_c[start_year]
    world.global_state.temperature_ocean = temperature_c[start_year] - 0.60
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


def _run_historical_backtest_member(
    *,
    state_csv: str | Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    policy_mode: str = DEFAULT_POLICY_MODE,
    enable_extreme_events: bool = False,
    decarb_rate_override: float | None = None,
    temperature_variability_sigma: float = 0.0,
    temperature_variability_seed: int = 0,
    temperature_variability_sign: float = 1.0,
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
        world.global_state._enable_temperature_variability = temperature_variability_sigma > 0.0
        world.global_state._temperature_variability_sigma = max(0.0, temperature_variability_sigma)
        world.global_state._temperature_variability_seed = int(temperature_variability_seed)
        world.global_state._temperature_variability_sign = float(temperature_variability_sign)

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
    predicted_temperature_values = [
        predicted_temperature_c[year] for year in range(start_year, end_year + 1)
    ]
    actual_temperature_values = [
        actual_temperature_c[year] for year in range(start_year, end_year + 1)
    ]
    temperature_residuals = [
        predicted_temperature_c[year] - actual_temperature_c[year]
        for year in range(start_year, end_year + 1)
    ]

    return HistoricalBacktestResult(
        start_year=start_year,
        end_year=end_year,
        policy_mode=policy_mode,
        enable_extreme_events=enable_extreme_events,
        state_csv=_display_path(state_csv_path),
        observed_fixture=_display_path(observed_path),
        temperature_ensemble_size=1,
        temperature_seed_base=int(temperature_variability_seed),
        temperature_variability_sigma=float(temperature_variability_sigma),
        gdp_rmse_trillions=_rmse(gdp_pairs),
        global_co2_rmse_gtco2=_rmse(co2_pairs),
        temperature_rmse_c=_rmse(temperature_pairs),
        temperature_bias_c=_mean(temperature_residuals),
        temperature_predicted_std_c=_std(predicted_temperature_values),
        temperature_observed_std_c=_std(actual_temperature_values),
        country_gdp_rmse_trillions=country_gdp_rmse_trillions,
        predicted_gdp_trillions=predicted_gdp_trillions,
        actual_gdp_trillions=actual_gdp_trillions,
        predicted_global_co2_gtco2=predicted_global_co2_gtco2,
        actual_global_co2_gtco2=actual_global_co2_gtco2,
        predicted_temperature_c=predicted_temperature_c,
        actual_temperature_c=actual_temperature_c,
    )


def _aggregate_historical_backtest_results(
    results: list[HistoricalBacktestResult],
    *,
    temperature_ensemble_size: int,
    temperature_seed_base: int,
    temperature_variability_sigma: float,
) -> HistoricalBacktestResult:
    if not results:
        raise ValueError("No historical backtest results to aggregate")
    if len(results) == 1:
        return results[0]

    anchor = results[0]
    years = range(anchor.start_year, anchor.end_year + 1)
    predicted_gdp_trillions = {
        year: {
            country: _mean([result.predicted_gdp_trillions[year][country] for result in results])
            for country in GDP_BACKTEST_ACTORS
        }
        for year in years
    }
    predicted_global_co2_gtco2 = {
        year: _mean([result.predicted_global_co2_gtco2[year] for result in results])
        for year in years
    }
    predicted_temperature_c = {
        year: _mean([result.predicted_temperature_c[year] for result in results])
        for year in years
    }
    actual_temperature_values = [anchor.actual_temperature_c[year] for year in years]

    return HistoricalBacktestResult(
        start_year=anchor.start_year,
        end_year=anchor.end_year,
        policy_mode=anchor.policy_mode,
        enable_extreme_events=anchor.enable_extreme_events,
        state_csv=anchor.state_csv,
        observed_fixture=anchor.observed_fixture,
        temperature_ensemble_size=int(temperature_ensemble_size),
        temperature_seed_base=int(temperature_seed_base),
        temperature_variability_sigma=float(temperature_variability_sigma),
        gdp_rmse_trillions=_mean([result.gdp_rmse_trillions for result in results]),
        global_co2_rmse_gtco2=_mean([result.global_co2_rmse_gtco2 for result in results]),
        temperature_rmse_c=_mean([result.temperature_rmse_c for result in results]),
        temperature_bias_c=_mean([result.temperature_bias_c for result in results]),
        temperature_predicted_std_c=_mean([result.temperature_predicted_std_c for result in results]),
        temperature_observed_std_c=_std(actual_temperature_values),
        country_gdp_rmse_trillions={
            country: _mean([result.country_gdp_rmse_trillions[country] for result in results])
            for country in GDP_BACKTEST_ACTORS
        },
        predicted_gdp_trillions=predicted_gdp_trillions,
        actual_gdp_trillions=anchor.actual_gdp_trillions,
        predicted_global_co2_gtco2=predicted_global_co2_gtco2,
        actual_global_co2_gtco2=anchor.actual_global_co2_gtco2,
        predicted_temperature_c=predicted_temperature_c,
        actual_temperature_c=anchor.actual_temperature_c,
    )


def run_historical_backtest(
    *,
    state_csv: str | Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    policy_mode: str = DEFAULT_POLICY_MODE,
    enable_extreme_events: bool = False,
    decarb_rate_override: float | None = None,
    temperature_variability_sigma_override: float | None = None,
    temperature_ensemble_size: int | None = None,
    temperature_seed_base: int = 0,
) -> HistoricalBacktestResult:
    temperature_variability_sigma = (
        cal.TEMP_NATURAL_VARIABILITY_SIGMA
        if temperature_variability_sigma_override is None
        else max(0.0, float(temperature_variability_sigma_override))
    )
    if temperature_ensemble_size is None:
        temperature_ensemble_size = cal.TEMP_BACKTEST_ENSEMBLE_SIZE if temperature_variability_sigma > 0.0 else 1
    temperature_ensemble_size = max(1, int(temperature_ensemble_size))

    member_results = [
        _run_historical_backtest_member(
            state_csv=state_csv,
            observed_fixture=observed_fixture,
            policy_mode=policy_mode,
            enable_extreme_events=enable_extreme_events,
            decarb_rate_override=decarb_rate_override,
            temperature_variability_sigma=temperature_variability_sigma,
            temperature_variability_seed=temperature_seed_base + ensemble_index // 2,
            temperature_variability_sign=(
                -1.0 if temperature_variability_sigma > 0.0 and ensemble_index % 2 else 1.0
            ),
        )
        for ensemble_index in range(temperature_ensemble_size)
    ]
    return _aggregate_historical_backtest_results(
        member_results,
        temperature_ensemble_size=temperature_ensemble_size,
        temperature_seed_base=temperature_seed_base,
        temperature_variability_sigma=temperature_variability_sigma,
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
        (
            "Temperature diagnostics: "
            f"bias={result.temperature_bias_c:+.3f}, "
            f"pred_std={result.temperature_predicted_std_c:.3f}, "
            f"obs_std={result.temperature_observed_std_c:.3f}, "
            f"ensemble={result.temperature_ensemble_size}, "
            f"sigma={result.temperature_variability_sigma:.3f}"
        ),
        "Worst GDP RMSE actors: "
        + ", ".join(f"{name}={value:.3f}" for name, value in worst_countries),
    ]
    return "\n".join(lines)


__all__ = [
    "compute_observed_global_co2_intensity",
    "estimate_observed_decarb_rate",
    "DEFAULT_BASELINE_FIXTURE",
    "DEFAULT_INITIAL_STATE_CSV",
    "DEFAULT_OBSERVED_FIXTURE",
    "GDP_BACKTEST_ACTORS",
    "HistoricalBacktestResult",
    "format_historical_backtest_result",
    "load_historical_observed_fixture",
    "load_historical_backtest_baseline",
    "run_historical_backtest",
]
