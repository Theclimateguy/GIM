# Построчные правки по трём главным замечаниям

Файл: `gim_paper 1.tex` (номера строк — по исходнику, присланному на рецензию).
Обозначения: **[ … ]** — плейсхолдер, куда нужно подставить фактически посчитанное число или факт; текст в плейсхолдерах сочинять нельзя. Правки №1–5 и №8–13 требуют только текста; №6–7 и №14 требуют одного дополнительного прогона пайплайна (это дёшево: у вас 30–50 мс на модельный год).

---

## Замечание 1 + 2. In-sample «валидация» и несоответствие аннотации телу статьи

Эти два замечания лечатся одним пакетом правок: аннотация, §3.2, §3.3, Таблица 3, Заключение.

### Правка 1 — Аннотация, стр. 116 (последние два предложения)

**Сейчас:**
```latex
The economic and climate blocks are calibrated on 1990--2023 historical data and pass
retrospective validation. The society, politics, and geopolitics blocks are assessed against
a more modest criterion -- improvement over consensus expert forecasts.
```

**Вариант A (минимальный, без новых расчётов — честная переформулировка):**
```latex
The climate block is calibrated against 1990--2023 observations and reproduces the observed
temperature and carbon record; the economic block is history-matched to 2015--2023 world
aggregates, and we report its in-sample fit together with skill against naive benchmarks.
The society, politics, and geopolitics blocks are assessed against a more modest criterion --
improvement over naive benchmarks (persistence, linear extrapolation, and base-rate forecasts).
```

**Вариант B (рекомендуемый, после добавления hold-out теста из Правок 3–4):**
```latex
The economic and climate blocks are calibrated on historical data and evaluated
retrospectively, including a temporal hold-out test in which parameters constrained on data
through [2019] are scored out-of-sample on [2020]--2023. The society, politics, and
geopolitics blocks are assessed against a more modest criterion -- improvement over naive
benchmarks (persistence, linear extrapolation, and base-rate forecasts).
```

Комментарий: формулировка «consensus expert forecasts» должна исчезнуть из аннотации в любом случае — в теле статьи такого сравнения нет (бенчмарки: persistence / линейная экстраполяция / base-rate, стр. 755–760, 786–787). Либо, если хотите её сохранить, добавьте само сравнение — см. Правку 5-опц.

### Правка 2 — §3.2, стр. 672–673

**Сейчас:**
```latex
Concretely, the constraining
observations are the 2015--2023 retrospective series of world product, world emissions, and
temperature.
```

**Заменить на:**
```latex
Concretely, the constraining
observations are the 2015--2023 retrospective series of world product, world emissions, and
temperature -- the same window for which the fit metrics of Section~\ref{sec:calib} are
reported, so those metrics characterize the quality of the \emph{in-sample} fit, not
out-of-sample skill; the hold-out design that measures the latter is described below.
```

### Правка 3 — §3.2, вставка нового абзаца после стр. 686 (после «…be accompanied by an explicit recalibration.»)

**Добавить:**
```latex
\emph{Temporal hold-out.} Because the retained parameter region is conditioned on the full
2015--2023 window, predictive adequacy is measured separately in a hold-out configuration:
history matching is rerun using only data through [2019], the resulting NROY region is
frozen, and the [2020]--2023 segment is scored strictly out-of-sample with no further
adjustment. Out-of-sample errors are reported alongside the in-sample fit in
Table~\ref{tab:backtest}. The held-out segment contains the COVID-19 shock, which no
structural model of this class anticipates endogenously; we therefore report the hold-out
skill both for the raw series and with the [2020] pandemic year excluded, and treat the
former as the harder, headline number.
```

Комментарий: разбиение 2015–2019 / 2020–2023 — самое естественное, но окно попадает на COVID. Честный ход — показать обе цифры (с 2020 и без), как в тексте выше. Альтернатива: калибровка до [2021], тест на [2022]–2023 — слабее, но чище от пандемии; тогда уберите последнее предложение.

### Правка 4 — §3.3, стр. 714–715 и Таблица 3

**Сейчас (стр. 715):**
```latex
Retrospective validation over 2015--2023 yields root-mean-square errors for gross
product, world emissions, and temperature.
```

**Заменить на:**
```latex
The in-sample retrospective fit over 2015--2023 (the history-matching window,
Section~\ref{sec:calib}) yields root-mean-square errors for gross product, world emissions,
and temperature; the temporal hold-out errors are given after them.
```

**Добавить после стр. 723 (после «…cures an ensemble under-dispersion present in earlier versions.»):**
```latex
In the temporal hold-out configuration (constraints through [2019], evaluation on
[2020]--2023), the out-of-sample errors are [X.XX] trillion USD for product, [X.XX]~Gt for
emissions, and [0.XXX]\,$^\circ$C for temperature; the corresponding skill against
persistence and linear extrapolation over the held-out segment is [$\pm$0.XX] and
[$\pm$0.XX]. [Если результат слабый — честно: e.g. ``As with the full-window comparison,
the structural model beats persistence for temperature but not linear extrapolation for
short smooth aggregates; the hold-out confirms that the in-sample fit is not an artefact of
conditioning.'']
```

**Таблица 3, подпись (стр. 736–737).** Сейчас: «The economic and climate blocks are checked by strict retrospective validation». Заменить на:
```latex
The economic and climate blocks are checked by retrospective evaluation: an in-sample fit
over the history-matching window and a temporal hold-out test (out-of-sample values in
parentheses).
```

**Таблица 3, строка Economy (стр. 746).** Сейчас:
```latex
Economy & PWT, WDI & retrospective RMSE, 2015--2023 & GDP $0.60$ trillion USD (Cobb--Douglas $0.60$) \\
```
Заменить на:
```latex
Economy & PWT, WDI & in-sample RMSE 2015--2023; hold-out [2020--2023] & GDP $0.60$ trillion
USD in-sample; [X.XX] out-of-sample \\
```
Аналогично строка Climate (стр. 747): добавить hold-out значения для CO$_2$ и $T$, либо явно пометить «in-sample» и сослаться на внешние якоря ECS/TCR (стр. 391–395), которые у климатического блока уже есть.

### Правка 5 — Заключение, стр. 1290–1291

**Сейчас:**
```latex
The economic and climate blocks are empirically anchored and pass retrospective
validation;
```

**Заменить на (вариант B):**
```latex
The economic and climate blocks are empirically anchored and retain their skill in a
temporal hold-out test;
```
**или (вариант A, без hold-out):**
```latex
The economic and climate blocks are empirically anchored, with the in-sample fit and
naive-benchmark comparisons reported in full;
```

### Правка 5-опц — если хотите сохранить «expert forecasts» в аннотации

Добавить в §3.3 после стр. 760 («…where a short-run smooth aggregate is hard to beat.»):
```latex
For reference against expert practice, the same window is scored against the [IMF World
Economic Outlook vintage-[year]] five-year-ahead projections: the model's product error of
[X.XX] trillion USD compares with [X.XX] for the WEO path, [and analogously for emissions
against the [IEA WEO / GCP] projections].
```
Только при фактически посчитанном сравнении; иначе — Правка 1, вариант A/B.

---

## Замечание 3. Conflict-AUC: vintage входов и обратная причинность

### Правка 6 — §3.3, стр. 773–777 (определение скора): зафиксировать vintage входов

**Сейчас (конец предложения, стр. 776–777):**
```latex
--- with no coefficient estimated from
conflict data. It is compared with the historical registry of armed conflicts over 1990--2023
across 57 countries \citep{sundberg2013}.
```

**Заменить на:**
```latex
--- with no coefficient estimated from
conflict data. Each input enters at its [указать фактический vintage: e.g. ``base-year 2023
value from the committed grounding files (WGI-derived stability, SWIID Gini, SIPRI-2023
military expenditure)'' / ``year-$t$ value along the historical run'']. The score is compared
with the historical registry of armed conflicts over 1990--2023 across 57 countries
\citep{sundberg2013}.
```

Комментарий: подставьте то, что реально делает код. Это предложение — ключ ко всему замечанию: без него читатель не может понять, что именно тест показывает.

### Правка 7 — §3.3, стр. 778–782: заменить абзац о «недопустимости утечки»

**Сейчас:**
```latex
The framing of the test is essential: what is evaluated is not an output
fitted to these same data but an \emph{input} risk indicator computed from observed country
characteristics and not tuned to the conflict registry. Hence there are no parameters trained on the
target variable and no associated information leakage, and a rolling train/test split is
unnecessary; the full set of 57 countries is evaluated as a whole.
```

**Заменить на:**
```latex
The framing of the test is essential: what is evaluated is not an output fitted to these
same data but an \emph{input} risk indicator not tuned to the conflict registry --- no
coefficient is estimated from conflict data, and the weights $(0.35,\,0.25,\,0.20,\,0.20)$
were fixed [указать фактическую провенанс: e.g. ``once, from the political-instability
literature, before any comparison with the registry; no alternative weightings were
evaluated against it'']. The absence of fitted parameters does not by itself exclude
leakage through the \emph{inputs}, however: regime stability and the military-expenditure
share are themselves affected by armed conflict, so inputs measured within or after the
evaluation window partly encode the outcome they rank. To bound this reverse-causation
channel, the score is additionally recomputed in a vintage-clean configuration: all inputs
are taken from data available up to [1999] only, and the ranking is evaluated against
conflict incidence over [2000]--2023. This yields AUC [0.XX] (bootstrap $95\,\%$ interval
$[0.XX;\,0.XX]$), [compared with / close to] the full-window value of $0.739$, so
[сформулировать по результату: e.g. ``the ranking skill is not an artefact of post-conflict
input contamination'' --- либо честно ослабить вывод, если AUC заметно падает]. The full set
of 57 countries is evaluated as a whole.
```

### Правка 8 — §3.3, стр. 795–798: увязать вывод с vintage-тестом

**Сейчас:**
```latex
The score
here is an \emph{input} indicator with zero parameters fitted to conflict outcomes; that it
nonetheless ranks (AUC $0.739$, $p\approx0.001$) and calibrates (monotone quintiles) against the
registry is evidence the model's internal state carries real conflict-relevant signal.
```

**Заменить на:**
```latex
The score
here is an \emph{input} indicator with zero parameters fitted to conflict outcomes; that it
ranks (AUC $0.739$, $p\approx0.001$), calibrates (monotone quintiles), and [retains its
skill in the vintage-clean configuration (AUC [0.XX])] is evidence the model's internal
state carries real conflict-relevant signal.
```

### Правка 9 — подпись к Рис. 2 (стр. 805–811)

В подпись панели (b) добавить после «…registry of armed conflicts of 1990--2023»:
```latex
(inputs at [vintage]; the vintage-clean variant is reported in the text)
```

### Правка 10 — Limitations, стр. 1042–1043

**Сейчас:**
```latex
conflict is intrinsically hard to predict, and the geopolitical block is
suitable only for relative risk (AUC ${\approx}0.74$).
```

**Заменить на:**
```latex
conflict is intrinsically hard to predict, and the geopolitical block is
suitable only for relative risk (AUC ${\approx}0.74$; the ranking evidence carries the
input-vintage caveat of Section~\ref{sec:calib} --- conflict itself degrades regime
stability and raises the military burden --- bounded there by the vintage-clean test).
```

---

## Сводка: что нужно посчитать, прежде чем вставлять правки

| # | Расчёт | Для правок | Оценка стоимости |
|---|--------|-----------|------------------|
| 1 | History matching на данных до [2019], out-of-sample RMSE и skill на [2020]–2023 (с 2020 и без) | 1B, 3, 4, 5 | один прогон существующего пайплайна |
| 2 | AUC/CI conflict-скора на входах vintage ≤ [1999] против конфликтов [2000]–2023 | 7, 8, 9 | пересбор входных файлов за исторический год + существующий bootstrap |
| 3 | (опция) сравнение с IMF WEO | 5-опц | сбор внешних прогнозов |

Правки 1A, 2, 5(вар. A), 6, 10 — чисто текстовые и не требуют расчётов; их можно внести немедленно. Ни один плейсхолдер нельзя заполнять «ожидаемым» числом — только фактическим результатом прогона.
