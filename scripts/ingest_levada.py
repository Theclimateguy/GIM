#!/usr/bin/env python3
"""Ingest Levada Center indicator tables (THE-126: trust differentiation data).

Two indicator pages, data embedded as HTML tables (row 0 = MM.YYYY dates):

  odobrenie-organov-vlasti  — monthly approval: Putin (president/PM), PM,
                              government, governors, State Duma
  polozhenie-del-v-strane   — "are things going in the right direction":
                              the wrong-direction share is a social_tension proxy

Outputs (data/blocks/RUS/series/):
  levada_approval_monthly.csv   entity, month, approve, disapprove
  levada_direction_monthly.csv  month, right_direction, wrong_direction

Raw HTML snapshots cached under data/blocks/RUS/raw/levada/.
Source: levada.ru (АНО "Левада-Центр"). Run from repo root.
"""

from __future__ import annotations

import csv
import re
import urllib.request
from pathlib import Path

RAW = Path("data/blocks/RUS/raw/levada")
OUT = Path("data/blocks/RUS/series")

PAGES = {
    "odobrenie": "https://www.levada.ru/indikatory/odobrenie-organov-vlasti/",
    "polozhenie": "https://www.levada.ru/indikatory/polozhenie-del-v-strane/",
}

# Entity of each data table on the approval page, keyed by the chart div id
# that precedes it (verified against the question text in the page source).
APPROVAL_ENTITIES = {
    "chart_div22251": "putin",
    "chart_div10868": "prime_minister",
    "chart_div6529": "government",
    "chart_div15562": "governors",
    "chart_div16180": "duma",
    "chart_div26611": "pm_medvedev_pre2020",
}


def fetch(name: str, url: str) -> str:
    cache = RAW / f"{name}.html"
    if cache.exists():
        return cache.read_text(errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    RAW.mkdir(parents=True, exist_ok=True)
    cache.write_text(html)
    return html


def parse_tables(html: str) -> list[tuple[str, list[str], list[list[str]]]]:
    """[(nearest chart_div id, dates, rows-of-values)] for every data table."""
    out = []
    for m in re.finditer(r"<table.*?</table>", html, re.S):
        ctx = html[max(0, m.start() - 1500):m.start()]
        ids = re.findall(r'id="(chart_div\d+)"', ctx)
        rows = re.findall(r"<tr.*?</tr>", m.group(0), re.S)
        if len(rows) < 2:
            continue
        def cells(row: str) -> list[str]:
            return [re.sub(r"<[^>]+>", "", c).strip()
                    for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
        header = cells(rows[0])
        dates = [c for c in header if re.fullmatch(r"\d{2}\.\d{4}", c)]
        if not dates:
            continue
        data_rows = [cells(r) for r in rows[1:]]
        out.append((ids[-1] if ids else "", dates, data_rows))
    return out


def month_key(mm_yyyy: str) -> str:
    mm, yyyy = mm_yyyy.split(".")
    return f"{yyyy}-{mm}"


RU_MON = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6,
          "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}

# column -> entity, per table index of the Sep-2023 institutional-trust
# release (full annual series 1994-2023, "вполне заслуживает доверия", %)
INSTITUTIONAL_TABLES = {
    0: {3: "government", 7: "president"},
    1: {1: "army", 2: "state_security"},
    3: {2: "big_business", 4: "banks"},
}


def _inst_year(label: str) -> int | None:
    label = label.strip()
    if re.fullmatch(r"\d{4}", label):
        return int(label)
    m = re.match(r"([а-я]{3})\.(\d{2})", label)
    if m and m.group(1) in RU_MON:
        yy = int(m.group(2))
        return 1900 + yy if yy >= 80 else 2000 + yy
    return None


def parse_institutional_trust() -> None:
    """Institutional trust (B6): annual 'вполне заслуживает доверия' shares
    for the institutions that map onto blocks — president/government →
    executive, army/state_security → security, banks → regulator,
    big_business → capital_elite. Source: the Sep-2023 release (the
    indicator page itself carries only a 2013-15 excerpt). Multiple
    observations within a year are averaged."""
    html = (RAW / "institutsionalnoe_doverie_2023.html").read_text(
        encoding="utf-8", errors="ignore")
    tables = re.findall(r"<table.*?</table>", html, re.S)
    acc: dict[tuple[str, int], list[float]] = {}
    for t_idx, colmap in INSTITUTIONAL_TABLES.items():
        rows = re.findall(r"<tr.*?</tr>", tables[t_idx], re.S)
        for row in rows:
            cells = [re.sub(r"<[^>]+>|&nbsp;|&#8212;", " ", c).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            if not cells:
                continue
            year = _inst_year(cells[0])
            if year is None:
                continue
            for col, entity in colmap.items():
                if col < len(cells) and re.fullmatch(r"\d+", cells[col]):
                    acc.setdefault((entity, year), []).append(float(cells[col]))
    out_rows = [{"entity": e, "year": y, "trust_pct": sum(v) / len(v)}
                for (e, y), v in sorted(acc.items())]
    with open(OUT / "levada_institutional_trust_annual.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["entity", "year", "trust_pct"])
        w.writeheader()
        w.writerows(out_rows)
    ents = sorted({r["entity"] for r in out_rows})
    print(f"levada_institutional_trust_annual.csv: {len(out_rows)} rows, "
          f"entities {ents}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    html = fetch("odobrenie", PAGES["odobrenie"])
    rows_out = []
    for div_id, dates, data in parse_tables(html):
        entity = APPROVAL_ENTITIES.get(div_id)
        if entity is None:
            continue
        # labels live in a separate header table; data rows are positional:
        # row 0 = approve, row 1 = disapprove (row 2 = no answer, unused)
        series = {}
        if len(data) >= 1:
            series["approve"] = data[0]
        if len(data) >= 2:
            series["disapprove"] = data[1]
        for i, dt in enumerate(dates):
            rec = {"entity": entity, "month": month_key(dt)}
            ok = False
            for k, vals in series.items():
                if i < len(vals) and vals[i].isdigit():
                    rec[k] = int(vals[i])
                    ok = True
            if ok:
                rows_out.append(rec)
    with open(OUT / "levada_approval_monthly.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["entity", "month", "approve", "disapprove"])
        w.writeheader()
        w.writerows(rows_out)
    ents = {r["entity"] for r in rows_out}
    print(f"levada_approval_monthly.csv: {len(rows_out)} rows, entities: {sorted(ents)}")

    html = fetch("polozhenie", PAGES["polozhenie"])
    rows_out = []
    for _div, dates, data in parse_tables(html):
        # positional: row 0 = right direction, row 1 = wrong direction
        if len(data) < 2:
            continue
        series = {"right_direction": data[0], "wrong_direction": data[1]}
        for i, dt in enumerate(dates):
            rec = {"month": month_key(dt)}
            ok = False
            for k, vals in series.items():
                if i < len(vals) and vals[i].isdigit():
                    rec[k] = int(vals[i])
                    ok = True
            if ok:
                rows_out.append(rec)
        break  # first matching table is the headline national series
    with open(OUT / "levada_direction_monthly.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["month", "right_direction", "wrong_direction"])
        w.writeheader()
        w.writerows(rows_out)
    print(f"levada_direction_monthly.csv: {len(rows_out)} rows")


def main_institutional() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parse_institutional_trust()


if __name__ == "__main__":
    main()
