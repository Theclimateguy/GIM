"""Probabilistic fan-chart rendering for ensemble results (Phase 1-E).

Renders the ensemble percentile bands as self-contained SVG fan charts in an HTML page
(p5-p95 outer band, p25-p75 inner band, p50 median line) for each headline metric. Pure
Python / SVG, no plotting dependency — consistent with the dashboard's HTML-generation style.
"""

from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence

from .ensemble import METRICS, EnsembleResult

_METRIC_LABELS = {
    "world_gdp": "World GDP (T$)",
    "world_population": "World population",
    "temperature": "Global temperature (°C above pre-industrial)",
    "co2": "Atmospheric CO₂ (GtCO₂)",
    "n_debt_crises": "Active debt crises (count)",
    "n_regime_crises": "Active regime crises (count)",
    "n_wars": "Active wars (count)",
    "mean_social_tension": "Mean social tension",
}

_W, _H = 560.0, 240.0
_ML, _MR, _MT, _MB = 64.0, 16.0, 30.0, 36.0


def _scale(value: float, lo: float, hi: float, a: float, b: float) -> float:
    if hi <= lo:
        return (a + b) / 2.0
    return a + (value - lo) / (hi - lo) * (b - a)


def _render_metric_svg(metric: str, bands: Dict[str, List[float]], years: Sequence[int]) -> str:
    n = len(years)
    xs = list(years)
    x_lo, x_hi = xs[0], xs[-1] if n > 1 else xs[0] + 1
    lows, highs = bands["p5"], bands["p95"]
    y_lo = min(lows)
    y_hi = max(highs)
    if y_hi == y_lo:
        y_hi = y_lo + 1.0
    pad = (y_hi - y_lo) * 0.08
    y_lo -= pad
    y_hi += pad

    def px(i: int) -> float:
        return _scale(xs[i], x_lo, x_hi, _ML, _W - _MR)

    def py(v: float) -> float:
        return _scale(v, y_lo, y_hi, _H - _MB, _MT)

    def band(low_key: str, high_key: str, fill: str) -> str:
        top = " ".join(f"{px(i):.1f},{py(bands[high_key][i]):.1f}" for i in range(n))
        bot = " ".join(f"{px(i):.1f},{py(bands[low_key][i]):.1f}" for i in range(n - 1, -1, -1))
        return f'<polygon points="{top} {bot}" fill="{fill}" stroke="none"/>'

    median = " ".join(f"{px(i):.1f},{py(bands['p50'][i]):.1f}" for i in range(n))

    # y-axis ticks
    ticks = []
    for f in (0.0, 0.5, 1.0):
        v = y_lo + f * (y_hi - y_lo)
        y = py(v)
        ticks.append(f'<line x1="{_ML:.0f}" y1="{y:.1f}" x2="{_W-_MR:.0f}" y2="{y:.1f}" stroke="#eee"/>')
        ticks.append(f'<text x="{_ML-6:.0f}" y="{y+3:.1f}" text-anchor="end" font-size="10" fill="#666">{v:.3g}</text>')
    # x-axis labels (first/last year)
    xlabs = (
        f'<text x="{px(0):.0f}" y="{_H-_MB+16:.0f}" text-anchor="middle" font-size="10" fill="#666">yr {xs[0]}</text>'
        f'<text x="{px(n-1):.0f}" y="{_H-_MB+16:.0f}" text-anchor="middle" font-size="10" fill="#666">yr {xs[-1]}</text>'
    )
    label = html.escape(_METRIC_LABELS.get(metric, metric))
    return (
        f'<svg viewBox="0 0 {_W:.0f} {_H:.0f}" xmlns="http://www.w3.org/2000/svg" class="fan">'
        f'<text x="{_ML:.0f}" y="18" font-size="13" font-weight="600" fill="#222">{label}</text>'
        f'{"".join(ticks)}'
        f'{band("p5","p95","#bcd5f0")}'
        f'{band("p25","p75","#7fb0e6")}'
        f'<polyline points="{median}" fill="none" stroke="#13386b" stroke-width="2"/>'
        f'{xlabs}'
        f'</svg>'
    )


def render_fan_charts(
    result: EnsembleResult,
    metrics: Optional[Sequence[str]] = None,
    title: str = "GIM17 Ensemble Projection",
) -> str:
    """Return a self-contained HTML page of SVG fan charts for the ensemble."""
    metrics = list(metrics) if metrics is not None else list(METRICS)
    panels = "".join(
        f'<div class="panel">{_render_metric_svg(m, result.bands[m], result.years)}</div>'
        for m in metrics
        if m in result.bands
    )
    cfg = result.to_dict()["config"]
    sub = (
        f"{result.n_members} members &middot; {cfg['years']} years &middot; "
        f"priors={html.escape(str(cfg['prior_set']))} &middot; seed={cfg['master_seed']}"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#222}"
        "h1{font-size:20px;margin:0 0 2px}.sub{color:#666;font-size:13px;margin-bottom:16px}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}"
        ".panel{border:1px solid #eee;border-radius:8px;padding:6px}.fan{width:100%;height:auto}"
        ".legend{font-size:12px;color:#555;margin-top:10px}"
        ".sw{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:middle;margin:0 4px 0 12px}"
        "</style></head><body>"
        f"<h1>{html.escape(title)}</h1><div class='sub'>{sub}</div>"
        "<div class='legend'>Bands:"
        "<span class='sw' style='background:#bcd5f0'></span>5–95%"
        "<span class='sw' style='background:#7fb0e6'></span>25–75%"
        "<span class='sw' style='background:#13386b'></span>median</div>"
        f"<div class='grid'>{panels}</div></body></html>"
    )


__all__ = ["render_fan_charts"]
