from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
import json
from pathlib import Path

from .core import calibration_params as cal
from .core.core import GTCO2_PER_PPM, WorldState
from .core.policy import make_policy_map
from .core.simulation import step_world
from .core.world_factory import make_world_from_csv
from .historical_backtest import (
    DEFAULT_INITIAL_STATE_CSV,
    DEFAULT_OBSERVED_FIXTURE,
    HistoricalBacktestResult,
    run_historical_backtest,
)
from .runtime import REPO_ROOT
from .state_projection import write_compiled_state_csv


@dataclass(frozen=True)
class RollingOriginWindow:
    origin_year: int
    train_start_year: int
    train_end_year: int
    validation_start_year: int
    validation_end_year: int
    origin_state_csv: str
    train_observed_fixture: str
    validation_observed_fixture: str


@dataclass(frozen=True)
class RollingPassResult:
    origin_year: int
    selected_economy_param_value: float
    selected_climate_param_value: float
    train_objective: float
    train_gdp_rmse_trillions: float
    train_global_co2_rmse_gtco2: float
    train_temperature_rmse_c: float
    validation_gdp_rmse_trillions: float
    validation_global_co2_rmse_gtco2: float
    validation_temperature_rmse_c: float
    validation_temperature_bias_c: float


@dataclass(frozen=True)
class RollingBacktestResult:
    created_at_utc: str
    base_state_csv: str
    observed_fixture: str
    origin_start_year: int
    origin_end_year: int
    economy_param_name: str
    climate_param_name: str
    economy_param_grid: list[float]
    climate_param_grid: list[float]
    objective_weights: dict[str, float]
    windows: list[RollingOriginWindow]
    passes: list[RollingPassResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "created_at_utc": self.created_at_utc,
            "base_state_csv": self.base_state_csv,
            "observed_fixture": self.observed_fixture,
            "origin_start_year": self.origin_start_year,
            "origin_end_year": self.origin_end_year,
            "economy_param_name": self.economy_param_name,
            "climate_param_name": self.climate_param_name,
            "economy_param_grid": list(self.economy_param_grid),
            "climate_param_grid": list(self.climate_param_grid),
            "objective_weights": dict(self.objective_weights),
            "windows": [asdict(item) for item in self.windows],
            "passes": [asdict(item) for item in self.passes],
        }


@dataclass(frozen=True)
class StageBCPassResult:
    origin_year: int
    selected_params: dict[str, float]
    train_objective: float
    train_gdp_rmse_trillions: float
    train_global_co2_rmse_gtco2: float
    train_temperature_rmse_c: float
    validation_objective: float
    validation_gdp_rmse_trillions: float
    validation_global_co2_rmse_gtco2: float
    validation_temperature_rmse_c: float
    validation_temperature_bias_c: float


@dataclass(frozen=True)
class StageBCResult:
    created_at_utc: str
    base_state_csv: str
    observed_fixture: str
    origin_start_year: int
    origin_end_year: int
    parameter_grids: dict[str, list[float]]
    objective_weights: dict[str, float]
    instability_penalty: float
    passes: list[StageBCPassResult]
    robust_params: dict[str, float]
    robust_score: float
    robust_mean_validation_objective: float
    robust_std_validation_objective: float
    robust_window_validation_scores: dict[int, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "created_at_utc": self.created_at_utc,
            "base_state_csv": self.base_state_csv,
            "observed_fixture": self.observed_fixture,
            "origin_start_year": self.origin_start_year,
            "origin_end_year": self.origin_end_year,
            "parameter_grids": {key: list(values) for key, values in self.parameter_grids.items()},
            "objective_weights": dict(self.objective_weights),
            "instability_penalty": float(self.instability_penalty),
            "passes": [asdict(item) for item in self.passes],
            "robust_params": dict(self.robust_params),
            "robust_score": float(self.robust_score),
            "robust_mean_validation_objective": float(self.robust_mean_validation_objective),
            "robust_std_validation_objective": float(self.robust_std_validation_objective),
            "robust_window_validation_scores": {
                int(year): float(score)
                for year, score in self.robust_window_validation_scores.items()
            },
        }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _coerce_int_keyed_series(raw: dict[str, float] | dict[int, float]) -> dict[int, float]:
    return {int(key): float(value) for key, value in raw.items()}


def _load_observed_fixture(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slice_observed_fixture(
    observed: dict[str, object],
    *,
    start_year: int,
    end_year: int,
) -> dict[str, object]:
    if end_year < start_year:
        raise ValueError(f"Invalid observed fixture slice {start_year}..{end_year}")

    gdp_all = observed["gdp_trillions_by_year"]
    co2_all = observed["global_co2_gtco2"]
    temp_all = observed["temperature_c_preindustrial"]
    ppm_all = observed["atmospheric_co2_ppm"]

    year_range = range(start_year, end_year + 1)
    return {
        "start_year": int(start_year),
        "end_year": int(end_year),
        "gdp_trillions_by_year": {
            str(year): {name: float(value) for name, value in gdp_all[str(year)].items()}
            for year in year_range
        },
        "global_co2_gtco2": {str(year): float(co2_all[str(year)]) for year in year_range},
        "temperature_c_preindustrial": {str(year): float(temp_all[str(year)]) for year in year_range},
        "atmospheric_co2_ppm": {str(year): float(ppm_all[str(year)]) for year in year_range},
        "source_notes": dict(observed.get("source_notes", {})),
    }


def _seed_historical_globals(world: WorldState, observed: dict[str, object], year: int) -> None:
    atmospheric_co2_ppm = _coerce_int_keyed_series(observed["atmospheric_co2_ppm"])
    temperature_c = _coerce_int_keyed_series(observed["temperature_c_preindustrial"])
    world.global_state.co2 = atmospheric_co2_ppm[year] * GTCO2_PER_PPM
    world.global_state.temperature_global = temperature_c[year]
    world.global_state.temperature_ocean = temperature_c[year] - 0.60
    world.global_state.carbon_pools = []
    world.global_state._calendar_year_base = year


def _anchor_world_to_observed(world: WorldState, observed: dict[str, object], year: int) -> None:
    gdp_observed_by_country = observed["gdp_trillions_by_year"][str(year)]
    for agent in world.agents.values():
        if agent.name in gdp_observed_by_country:
            agent.economy.gdp = float(gdp_observed_by_country[agent.name])

    co2_target = float(observed["global_co2_gtco2"][str(year)])
    co2_now = sum(float(agent.climate.co2_annual_emissions) for agent in world.agents.values())
    if co2_now > 0.0 and co2_target >= 0.0:
        scale = co2_target / co2_now
        for agent in world.agents.values():
            agent.climate.co2_annual_emissions = max(0.0, float(agent.climate.co2_annual_emissions) * scale)

    _seed_historical_globals(world, observed, year)


def build_origin_windows(
    *,
    output_dir: str | Path,
    base_state_csv: str | Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    policy_mode: str = "simple",
    origin_start_year: int | None = None,
    origin_end_year: int | None = None,
) -> list[RollingOriginWindow]:
    output_root = Path(output_dir).expanduser().resolve()
    states_dir = output_root / "origin_states"
    fixtures_dir = output_root / "fixtures"
    states_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    observed_path = Path(observed_fixture).expanduser().resolve()
    observed = _load_observed_fixture(observed_path)
    observed_start = int(observed["start_year"])
    observed_end = int(observed["end_year"])

    start_year = observed_start if origin_start_year is None else int(origin_start_year)
    end_year = observed_end - 1 if origin_end_year is None else int(origin_end_year)
    if start_year < observed_start or end_year > observed_end - 1:
        raise ValueError(
            f"Origin range {start_year}..{end_year} must be within {observed_start}..{observed_end - 1}"
        )
    if end_year < start_year:
        raise ValueError(f"Invalid origin range {start_year}..{end_year}")

    world = make_world_from_csv(str(Path(base_state_csv).expanduser().resolve()))
    _seed_historical_globals(world, observed, observed_start)
    policies = make_policy_map(world.agents.keys(), mode=policy_mode)

    windows: list[RollingOriginWindow] = []
    for year in range(observed_start, end_year + 1):
        if year > observed_start:
            world = step_world(world, policies, enable_extreme_events=False)
        _anchor_world_to_observed(world, observed, year)

        if year < start_year:
            continue

        state_path = states_dir / f"historical_backtest_state_{year}.csv"
        write_compiled_state_csv(world, state_path)

        train_fixture = _slice_observed_fixture(observed, start_year=observed_start, end_year=year)
        train_fixture_path = fixtures_dir / f"observed_train_{observed_start}_{year}.json"
        train_fixture_path.write_text(json.dumps(train_fixture, indent=2), encoding="utf-8")

        val_fixture = _slice_observed_fixture(observed, start_year=year, end_year=year + 1)
        val_fixture_path = fixtures_dir / f"observed_val_{year}_{year + 1}.json"
        val_fixture_path.write_text(json.dumps(val_fixture, indent=2), encoding="utf-8")

        windows.append(
            RollingOriginWindow(
                origin_year=year,
                train_start_year=observed_start,
                train_end_year=year,
                validation_start_year=year,
                validation_end_year=year + 1,
                origin_state_csv=_display_path(state_path),
                train_observed_fixture=_display_path(train_fixture_path),
                validation_observed_fixture=_display_path(val_fixture_path),
            )
        )

    metadata_path = output_root / "origin_windows.json"
    metadata_path.write_text(
        json.dumps(
            {
                "created_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "base_state_csv": _display_path(Path(base_state_csv).expanduser().resolve()),
                "observed_fixture": _display_path(observed_path),
                "origin_start_year": start_year,
                "origin_end_year": end_year,
                "windows": [asdict(window) for window in windows],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return windows


def _default_param_grid(center: float, *, points: int = 9, span: float = 0.4) -> list[float]:
    low = max(0.0, center * (1.0 - span))
    high = center * (1.0 + span)
    if points <= 1 or high <= low:
        return [float(center)]
    step = (high - low) / (points - 1)
    return [float(low + idx * step) for idx in range(points)]


class _temporary_calibration_overrides:
    def __init__(self, overrides: dict[str, float]):
        self._overrides = dict(overrides)
        self._originals: dict[str, float] = {}

    def __enter__(self):
        keys = set(self._overrides.keys())
        if "DECARB_RATE_STRUCTURAL" in keys or "DECARB_RATE" in keys:
            keys.add("DECARB_RATE_STRUCTURAL")
            keys.add("DECARB_RATE")
        for key in keys:
            self._originals[key] = float(getattr(cal, key))

        for key, value in self._overrides.items():
            setattr(cal, key, float(value))
        if "DECARB_RATE_STRUCTURAL" in self._overrides:
            setattr(cal, "DECARB_RATE", float(self._overrides["DECARB_RATE_STRUCTURAL"]))
        if "DECARB_RATE" in self._overrides:
            setattr(cal, "DECARB_RATE_STRUCTURAL", float(self._overrides["DECARB_RATE"]))
        return self

    def __exit__(self, exc_type, exc, tb):
        for key, value in self._originals.items():
            setattr(cal, key, value)


def _score_mean_std(scores: list[float]) -> tuple[float, float]:
    if not scores:
        return 0.0, 0.0
    mean = sum(scores) / len(scores)
    variance = sum((value - mean) ** 2 for value in scores) / len(scores)
    return float(mean), float(variance ** 0.5)


def _objective_score(
    result: HistoricalBacktestResult,
    *,
    gdp_weight: float,
    co2_weight: float,
    temp_weight: float,
) -> float:
    return (
        gdp_weight * result.gdp_rmse_trillions
        + co2_weight * result.global_co2_rmse_gtco2
        + temp_weight * result.temperature_rmse_c
    )


def run_stepwise_rolling_backtest(
    *,
    output_dir: str | Path,
    base_state_csv: str | Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    policy_mode: str = "simple",
    origin_start_year: int | None = None,
    origin_end_year: int | None = None,
    economy_param_name: str = "TFP_RD_SHARE_SENS",
    climate_param_name: str = "DECARB_RATE_STRUCTURAL",
    economy_param_grid: list[float] | None = None,
    climate_param_grid: list[float] | None = None,
    gdp_weight: float = 0.10,
    co2_weight: float = 1.00,
    temp_weight: float = 10.00,
) -> RollingBacktestResult:
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    windows = build_origin_windows(
        output_dir=output_root,
        base_state_csv=base_state_csv,
        observed_fixture=observed_fixture,
        policy_mode=policy_mode,
        origin_start_year=origin_start_year,
        origin_end_year=origin_end_year,
    )
    if not windows:
        raise ValueError("No origin windows were created")

    if not hasattr(cal, economy_param_name):
        raise ValueError(f"Unknown economy calibration parameter: {economy_param_name}")
    if not hasattr(cal, climate_param_name):
        raise ValueError(f"Unknown climate calibration parameter: {climate_param_name}")

    econ_center = float(getattr(cal, economy_param_name))
    climate_center = float(getattr(cal, climate_param_name))
    econ_grid = (
        [float(value) for value in economy_param_grid]
        if economy_param_grid
        else _default_param_grid(econ_center)
    )
    clim_grid = (
        [float(value) for value in climate_param_grid]
        if climate_param_grid
        else _default_param_grid(climate_center)
    )
    if not econ_grid:
        raise ValueError("Economy calibration grid is empty")
    if not clim_grid:
        raise ValueError("Climate calibration grid is empty")

    passes: list[RollingPassResult] = []
    for window in windows:
        train_path = REPO_ROOT / window.train_observed_fixture
        val_path = REPO_ROOT / window.validation_observed_fixture
        state_path = REPO_ROOT / window.origin_state_csv

        best_score: float | None = None
        best_econ_value = econ_center
        best_clim_value = climate_center
        best_train_result: HistoricalBacktestResult | None = None
        for econ_candidate, clim_candidate in product(econ_grid, clim_grid):
            with _temporary_calibration_overrides(
                {
                    economy_param_name: float(econ_candidate),
                    climate_param_name: float(clim_candidate),
                }
            ):
                train_result = run_historical_backtest(
                    state_csv=base_state_csv,
                    observed_fixture=train_path,
                    policy_mode=policy_mode,
                    enable_extreme_events=False,
                    decarb_rate_override=None,
                    temperature_variability_sigma_override=0.0,
                    temperature_ensemble_size=1,
                )
            score = _objective_score(
                train_result,
                gdp_weight=gdp_weight,
                co2_weight=co2_weight,
                temp_weight=temp_weight,
            )
            if best_score is None or score < best_score - 1e-12:
                best_score = score
                best_econ_value = float(econ_candidate)
                best_clim_value = float(clim_candidate)
                best_train_result = train_result
                continue

            if best_score is not None and abs(score - best_score) <= 1e-12:
                candidate_distance = (
                    abs(float(econ_candidate) - econ_center) / max(abs(econ_center), 1e-9)
                    + abs(float(clim_candidate) - climate_center) / max(abs(climate_center), 1e-9)
                )
                best_distance = (
                    abs(best_econ_value - econ_center) / max(abs(econ_center), 1e-9)
                    + abs(best_clim_value - climate_center) / max(abs(climate_center), 1e-9)
                )
                if candidate_distance < best_distance:
                    best_score = score
                    best_econ_value = float(econ_candidate)
                    best_clim_value = float(clim_candidate)
                    best_train_result = train_result

        assert best_train_result is not None
        with _temporary_calibration_overrides(
            {
                economy_param_name: best_econ_value,
                climate_param_name: best_clim_value,
            }
        ):
            val_result = run_historical_backtest(
                state_csv=state_path,
                observed_fixture=val_path,
                policy_mode=policy_mode,
                enable_extreme_events=False,
                decarb_rate_override=None,
                temperature_variability_sigma_override=0.0,
                temperature_ensemble_size=1,
            )

        passes.append(
            RollingPassResult(
                origin_year=window.origin_year,
                selected_economy_param_value=best_econ_value,
                selected_climate_param_value=best_clim_value,
                train_objective=float(best_score or 0.0),
                train_gdp_rmse_trillions=best_train_result.gdp_rmse_trillions,
                train_global_co2_rmse_gtco2=best_train_result.global_co2_rmse_gtco2,
                train_temperature_rmse_c=best_train_result.temperature_rmse_c,
                validation_gdp_rmse_trillions=val_result.gdp_rmse_trillions,
                validation_global_co2_rmse_gtco2=val_result.global_co2_rmse_gtco2,
                validation_temperature_rmse_c=val_result.temperature_rmse_c,
                validation_temperature_bias_c=val_result.temperature_bias_c,
            )
        )

    result = RollingBacktestResult(
        created_at_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        base_state_csv=_display_path(Path(base_state_csv).expanduser().resolve()),
        observed_fixture=_display_path(Path(observed_fixture).expanduser().resolve()),
        origin_start_year=min(window.origin_year for window in windows),
        origin_end_year=max(window.origin_year for window in windows),
        economy_param_name=str(economy_param_name),
        climate_param_name=str(climate_param_name),
        economy_param_grid=[float(value) for value in econ_grid],
        climate_param_grid=[float(value) for value in clim_grid],
        objective_weights={"gdp": float(gdp_weight), "co2": float(co2_weight), "temperature": float(temp_weight)},
        windows=windows,
        passes=passes,
    )

    result_path = output_root / "rolling_backtest_stepwise.json"
    result_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return result


def format_rolling_backtest_result(result: RollingBacktestResult) -> str:
    if not result.passes:
        return "Rolling backtest: no passes"

    mean_val_gdp = sum(p.validation_gdp_rmse_trillions for p in result.passes) / len(result.passes)
    mean_val_co2 = sum(p.validation_global_co2_rmse_gtco2 for p in result.passes) / len(result.passes)
    mean_val_temp = sum(p.validation_temperature_rmse_c for p in result.passes) / len(result.passes)
    econ_values = [p.selected_economy_param_value for p in result.passes]
    clim_values = [p.selected_climate_param_value for p in result.passes]
    lines = [
        f"Rolling backtest origins {result.origin_start_year}-{result.origin_end_year} ({len(result.passes)} passes)",
        f"Mean one-step GDP RMSE (trillions USD): {mean_val_gdp:.3f}",
        f"Mean one-step global CO2 RMSE (GtCO2): {mean_val_co2:.3f}",
        f"Mean one-step temperature RMSE (deg C): {mean_val_temp:.3f}",
        (
            f"Selected {result.economy_param_name} range: "
            f"[{min(econ_values):.6f}, {max(econ_values):.6f}]"
        ),
        (
            f"Selected {result.climate_param_name} range: "
            f"[{min(clim_values):.6f}, {max(clim_values):.6f}]"
        ),
    ]
    return "\n".join(lines)


def _default_block4_param_grids(
    *,
    economy1: str,
    economy2: str,
    climate1: str,
    climate2: str,
) -> dict[str, list[float]]:
    return {
        economy1: _default_param_grid(float(getattr(cal, economy1)), points=3, span=0.4),
        economy2: _default_param_grid(float(getattr(cal, economy2)), points=3, span=0.4),
        climate1: _default_param_grid(float(getattr(cal, climate1)), points=3, span=0.4),
        climate2: _default_param_grid(float(getattr(cal, climate2)), points=3, span=0.4),
    }


def _iter_candidate_params(parameter_grids: dict[str, list[float]]) -> list[dict[str, float]]:
    names = list(parameter_grids.keys())
    values = [parameter_grids[name] for name in names]
    return [
        {name: float(value) for name, value in zip(names, combo)}
        for combo in product(*values)
    ]


def run_block4_stage_bc(
    *,
    output_dir: str | Path,
    base_state_csv: str | Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: str | Path = DEFAULT_OBSERVED_FIXTURE,
    policy_mode: str = "simple",
    origin_start_year: int | None = None,
    origin_end_year: int | None = None,
    economy_param_1: str = "TFP_RD_SHARE_SENS",
    economy_param_2: str = "GAMMA_ENERGY",
    climate_param_1: str = "DECARB_RATE_STRUCTURAL",
    climate_param_2: str = "HEAT_CAP_SURFACE",
    parameter_grids: dict[str, list[float]] | None = None,
    gdp_weight: float = 0.10,
    co2_weight: float = 1.00,
    temp_weight: float = 10.00,
    instability_penalty: float = 0.50,
) -> StageBCResult:
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    windows = build_origin_windows(
        output_dir=output_root,
        base_state_csv=base_state_csv,
        observed_fixture=observed_fixture,
        policy_mode=policy_mode,
        origin_start_year=origin_start_year,
        origin_end_year=origin_end_year,
    )
    if not windows:
        raise ValueError("No origin windows were created")

    param_names = [economy_param_1, economy_param_2, climate_param_1, climate_param_2]
    if len(set(param_names)) != 4:
        raise ValueError("Stage B/C requires four distinct parameters (2 economy + 2 climate)")
    for name in param_names:
        if not hasattr(cal, name):
            raise ValueError(f"Unknown calibration parameter: {name}")

    grids = (
        {name: [float(v) for v in values] for name, values in parameter_grids.items()}
        if parameter_grids
        else _default_block4_param_grids(
            economy1=economy_param_1,
            economy2=economy_param_2,
            climate1=climate_param_1,
            climate2=climate_param_2,
        )
    )
    if set(grids.keys()) != set(param_names):
        raise ValueError(
            "parameter_grids keys must match the 4 selected parameter names exactly"
        )
    for name, values in grids.items():
        if not values:
            raise ValueError(f"Empty grid for parameter {name}")

    candidates = _iter_candidate_params(grids)
    passes: list[StageBCPassResult] = []
    for window in windows:
        train_path = REPO_ROOT / window.train_observed_fixture
        val_path = REPO_ROOT / window.validation_observed_fixture
        state_path = REPO_ROOT / window.origin_state_csv

        best_candidate: dict[str, float] | None = None
        best_score: float | None = None
        best_train_result: HistoricalBacktestResult | None = None
        for candidate in candidates:
            with _temporary_calibration_overrides(candidate):
                train_result = run_historical_backtest(
                    state_csv=base_state_csv,
                    observed_fixture=train_path,
                    policy_mode=policy_mode,
                    enable_extreme_events=False,
                    decarb_rate_override=None,
                    temperature_variability_sigma_override=0.0,
                    temperature_ensemble_size=1,
                )
            score = _objective_score(
                train_result,
                gdp_weight=gdp_weight,
                co2_weight=co2_weight,
                temp_weight=temp_weight,
            )
            if best_score is None or score < best_score - 1e-12:
                best_score = score
                best_candidate = dict(candidate)
                best_train_result = train_result

        assert best_candidate is not None
        assert best_train_result is not None
        with _temporary_calibration_overrides(best_candidate):
            val_result = run_historical_backtest(
                state_csv=state_path,
                observed_fixture=val_path,
                policy_mode=policy_mode,
                enable_extreme_events=False,
                decarb_rate_override=None,
                temperature_variability_sigma_override=0.0,
                temperature_ensemble_size=1,
            )
        val_objective = _objective_score(
            val_result,
            gdp_weight=gdp_weight,
            co2_weight=co2_weight,
            temp_weight=temp_weight,
        )
        passes.append(
            StageBCPassResult(
                origin_year=window.origin_year,
                selected_params=best_candidate,
                train_objective=float(best_score or 0.0),
                train_gdp_rmse_trillions=best_train_result.gdp_rmse_trillions,
                train_global_co2_rmse_gtco2=best_train_result.global_co2_rmse_gtco2,
                train_temperature_rmse_c=best_train_result.temperature_rmse_c,
                validation_objective=val_objective,
                validation_gdp_rmse_trillions=val_result.gdp_rmse_trillions,
                validation_global_co2_rmse_gtco2=val_result.global_co2_rmse_gtco2,
                validation_temperature_rmse_c=val_result.temperature_rmse_c,
                validation_temperature_bias_c=val_result.temperature_bias_c,
            )
        )

    robust_best_score: float | None = None
    robust_best_candidate: dict[str, float] | None = None
    robust_best_mean = 0.0
    robust_best_std = 0.0
    robust_best_by_window: dict[int, float] = {}
    for candidate in candidates:
        by_window: dict[int, float] = {}
        for window in windows:
            val_path = REPO_ROOT / window.validation_observed_fixture
            state_path = REPO_ROOT / window.origin_state_csv
            with _temporary_calibration_overrides(candidate):
                val_result = run_historical_backtest(
                    state_csv=state_path,
                    observed_fixture=val_path,
                    policy_mode=policy_mode,
                    enable_extreme_events=False,
                    decarb_rate_override=None,
                    temperature_variability_sigma_override=0.0,
                    temperature_ensemble_size=1,
                )
            by_window[window.origin_year] = _objective_score(
                val_result,
                gdp_weight=gdp_weight,
                co2_weight=co2_weight,
                temp_weight=temp_weight,
            )
        score_values = list(by_window.values())
        mean_score, std_score = _score_mean_std(score_values)
        robust_score = mean_score + float(instability_penalty) * std_score
        if robust_best_score is None or robust_score < robust_best_score - 1e-12:
            robust_best_score = robust_score
            robust_best_candidate = dict(candidate)
            robust_best_mean = mean_score
            robust_best_std = std_score
            robust_best_by_window = dict(by_window)

    assert robust_best_candidate is not None
    assert robust_best_score is not None
    result = StageBCResult(
        created_at_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        base_state_csv=_display_path(Path(base_state_csv).expanduser().resolve()),
        observed_fixture=_display_path(Path(observed_fixture).expanduser().resolve()),
        origin_start_year=min(window.origin_year for window in windows),
        origin_end_year=max(window.origin_year for window in windows),
        parameter_grids={name: [float(v) for v in grids[name]] for name in param_names},
        objective_weights={"gdp": float(gdp_weight), "co2": float(co2_weight), "temperature": float(temp_weight)},
        instability_penalty=float(instability_penalty),
        passes=passes,
        robust_params=robust_best_candidate,
        robust_score=float(robust_best_score),
        robust_mean_validation_objective=float(robust_best_mean),
        robust_std_validation_objective=float(robust_best_std),
        robust_window_validation_scores=robust_best_by_window,
    )
    result_path = output_root / "stage_bc_block4.json"
    result_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return result


def format_stage_bc_result(result: StageBCResult) -> str:
    if not result.passes:
        return "Stage B/C block-4: no passes"
    mean_val_gdp = sum(p.validation_gdp_rmse_trillions for p in result.passes) / len(result.passes)
    mean_val_co2 = sum(p.validation_global_co2_rmse_gtco2 for p in result.passes) / len(result.passes)
    mean_val_temp = sum(p.validation_temperature_rmse_c for p in result.passes) / len(result.passes)
    params = ", ".join(f"{name}={value:.6f}" for name, value in result.robust_params.items())
    return "\n".join(
        [
            f"Stage B/C block-4 origins {result.origin_start_year}-{result.origin_end_year} ({len(result.passes)} passes)",
            f"Mean one-step GDP RMSE (trillions USD): {mean_val_gdp:.3f}",
            f"Mean one-step global CO2 RMSE (GtCO2): {mean_val_co2:.3f}",
            f"Mean one-step temperature RMSE (deg C): {mean_val_temp:.3f}",
            (
                "Robust set objective: "
                f"{result.robust_score:.4f} "
                f"(mean={result.robust_mean_validation_objective:.4f}, "
                f"std={result.robust_std_validation_objective:.4f}, "
                f"penalty={result.instability_penalty:.2f})"
            ),
            f"Robust parameters: {params}",
        ]
    )


__all__ = [
    "RollingBacktestResult",
    "RollingOriginWindow",
    "RollingPassResult",
    "StageBCPassResult",
    "StageBCResult",
    "build_origin_windows",
    "format_rolling_backtest_result",
    "format_stage_bc_result",
    "run_block4_stage_bc",
    "run_stepwise_rolling_backtest",
]
