# Block-state storage protocol (ADR, THE-114)

Status: accepted 2026-08-03. Scope: субнациональный блочный слой (спецификация v0.2).

## Решение

Блочное состояние хранится **отдельно** от `data/agent_states_operational.csv`, в long-формате:

```
data/blocks/block_states.csv          # канонический long-формат, все агенты
data/blocks/<AGENT>/block_states_<AGENT>.csv   # wide-снапшот на базовый год (зеркало странового CSV)
data/blocks/<AGENT>/raw/…             # сырьё по источникам (манифест SOURCES.md)
data/blocks/<AGENT>/series/…          # нормализованные tidy-ряды из сырья
```

Схема канонического long-файла:

| Колонка | Тип | Примечание |
|---|---|---|
| `agent_id` | str | ISO3 странового агента (RUS) |
| `block_key` | str | из словаря блоков §3 (`regulator`, `executive`, …) |
| `year` | int | календарный год |
| `quarter` | int/пусто | 1–4; пусто = годовое значение (§8: годовое ядро не меняется) |
| `field` | str | имя поля из `agent_states_operational.csv` (реестр классов — `gim/blocks/field_registry.py`) |
| `value` | float/str | точечное значение |
| `value_low`, `value_high` | float/пусто | интервал неопределённости (обязателен для security-блока RUS, §5) |
| `source` | str | код источника из SOURCES.md (cbr, minfin, rosstat, emiss, sipri, owid, est) |
| `quality` | enum | `primary` / `estimate` / `interpolated` |

## Почему не расширение странового CSV

1. Годовое ядро GIM18 и все его читатели (`make_world_from_csv`, бэктест) не трогаются — требование §1/§8.
2. Блочный слой добавляет оси (block, quarter, later territory) — в wide-формате это 5–7× строк
   и комбинаторный взрыв колонок; long-формат расширяем на клетки блок×территория (§7) без миграции.
3. Провенанс на точку (`source`, `quality`, интервал) невозможен в wide-схеме без утроения колонок.

## Почему CSV, а не parquet

Ядро GIM18 — stdlib-only (см. pyproject: pandas — только optional `analysis`). Валидатор §9 должен
читать блочное состояние без pandas. Объём пилота (5 блоков × ~30 полей × 9 лет × 4 квартала ≈ 5–10k
строк) для CSV тривиален. Parquet пересмотрим при генерализации на 57 агентов.

## Wide-снапшот

`block_states_<AGENT>.csv` повторяет схему странового CSV (те же 35 колонок, строки = блоки).
Генерируется из long-файла на базовый год; не редактируется руками. Роль: вход для свёртки в страновой
хэш и визуальная сверка со страновой строкой.
