# What the model is made of — the layers, in plain language

The Global Integrated Model is a year-by-year simulation of the world, run as a set of countries
(about fifty real countries plus a few regional groupings) that interact. Each year every country's
economy, society, politics, environment and relations with other countries are updated, and the
results feed into the next year. This page describes each layer of the model in plain language:
what it can do, and where its limits are. No jargon, no abbreviations.

A useful way to read it: the **economy** and the **climate** are the two strongest, best-validated
layers; the **society, politics, geopolitics and culture** layers are the model's distinctive
feature but are harder to pin down with data, so they are validated more modestly. Many of the more
speculative mechanisms are switches that are turned off by default, so the model's standard ("headline")
behaviour stays anchored to historical data, and those switches are explored separately as
uncertainty.

---

## 1. Economy

**What it does.** Each country produces output each year from three things it has: its accumulated
capital (factories, machines, infrastructure), its working population, and the energy it uses.
Capital grows when the country saves and invests, and wears out over time. Productivity (how much
output you get from the same inputs) grows slowly over time and a little faster when a country
spends on research. The model also tracks inflation, unemployment, the government's budget and its
debt, the interest rate set by the central bank, and trade flows between countries. It reproduces
the last decade of real history (2015–2023) for national income, so the economic engine is
grounded, not invented.

**Limits.** The recipe that turns capital, labour and energy into output now represents how hard it
is to swap one factor for another — in particular, when energy gets expensive the economy shifts
toward capital and uses less energy (a calibrated capital–energy substitution), which is what lets a
carbon price realistically reshuffle the economy. (This replaced the earlier bare textbook formula
and actually improved the fit to history.) What remains: markets do not yet fully "clear" — prices
adjust gradually rather than instantly balancing supply and demand (the next development step);
households and firms look at the recent past rather than truly anticipating the future; and long-run
growth is only loosely pinned down by the short history available. These are honest simplifications,
not errors.

## 2. Climate and the carbon cycle

**What it does.** The output the economy produces comes with carbon dioxide emissions. Those
emissions accumulate in the atmosphere and decay over many timescales, other greenhouse gases are
accounted for, and the resulting warming is computed with a standard physical heat-balance model of
the planet's surface and ocean. There is also a source of emissions from land use (deforestation
and similar), and an optional set of self-reinforcing feedbacks (for example thawing permafrost
releasing more carbon as it warms). This layer is calibrated to match the mainstream scientific
assessment: it reproduces the accepted sensitivity of temperature to carbon dioxide and tracks the
observed warming and carbon record from 1990 to 2023.

**Limits.** The strongest feedbacks (permafrost, abrupt carbon release) are deeply uncertain, so by
default they are kept out of the headline run and explored only as tail risks. The model matches the
headline climate numbers but is not a full Earth-system model — it is a fast, calibrated
approximation, which is appropriate for an economy-and-society model but not a substitute for a
dedicated climate model.

## 3. Climate damage and the cost of carbon

**What it does.** Warming feeds back into the economy as damage: higher temperatures reduce output,
with the size of the effect taken from the empirical climate-economics literature. From this the
model computes the "social cost of carbon" — the economic damage caused by emitting one extra tonne
of carbon dioxide — which is the standard yardstick for climate policy. A carbon price, when
applied, makes energy more expensive and pushes the economy to use less of it, lowering emissions.

**Limits.** Damage estimates are genuinely uncertain across the whole field; the model carries that
uncertainty explicitly (a range, not a single number) and can switch on a stronger "growth" form of
damage. The headline cost-of-carbon figure sits a little above the most-cited official estimates,
because the model's damages are on the higher (but still evidence-supported) side.

## 4. Resources — energy, food and metals

**What it does.** Each country has reserves, production and consumption of energy, food and metals,
and there are world prices for each that rise when demand outstrips supply. Resource scarcity feeds
into prices, which feed into inflation and into the economy.

**Limits.** Prices adjust gradually by a rule rather than by fully balancing the market each year
(an optional mode makes the energy/resource market clear properly). Resources are represented at a
broad level, not as detailed sector-by-sector energy systems.

## 5. Society and politics

**What it does.** For each country the model tracks public trust in government, social tension,
income inequality, the legitimacy of institutions, and pressure from protests. These respond to the
economy — for instance, rising inflation and unemployment increase tension and erode trust, and high
inequality amplifies that. Society and politics in turn feed back into stability and the risk of
crises.

**Limits.** Unlike the economy and climate, there is no single authoritative dataset that says
"given these conditions, this much unrest will follow." So these relationships are built from expert
judgement and broad evidence, and validated by a more modest standard: does the model rank risk
better than simply guessing the historical average? (It does — see the geopolitics layer.) These
layers should be read as informed, directionally-sound, and uncertain — not as precise forecasts.

## 6. Geopolitics — relations between countries

**What it does.** Every pair of countries has a relationship: how much they trade, whether they are
allied, how much conflict or tension exists between them, whether they are at war, and whether
sanctions are in place. Each country has a military capability, which is grounded in real, observable
national-power data rather than an arbitrary number. Conflicts, sanctions and wars have economic
consequences (lost output, disrupted trade) that flow back into the other layers.

**Limits.** Conflict is intrinsically hard to predict. The model's measure of how conflict-prone a
country is was tested against the standard historical record of armed conflicts (1990–2023): it
clearly ranks the genuinely conflict-affected countries above the calm ones (well better than
chance), which is the honest bar for this kind of layer. It is good for relative risk and scenario
exploration, not for predicting specific wars on specific dates.

## 7. Culture

**What it does.** A small set of cultural traits — most importantly how individualistic a society
is, how much it avoids uncertainty, how long-term its outlook is, and how hierarchical it is — plus
whether a country is a democracy or an autocracy, feed into economic and social behaviour (for
example, how strongly a society reacts to economic stress). The traits that genuinely move outcomes
are kept; ones that were carried but never actually affected anything were removed, so the model
does not pretend to cultural detail it does not really use.

**Limits.** The links from culture to behaviour are theory-based and validated only in sign and
rough size, not precisely. They are switchable and kept modest on purpose.

## 8. Risk and crises

**What it does.** On top of the smooth year-to-year dynamics, the model detects and applies
discrete crises: government debt crises, currency crises, regime collapse, and climate extreme
events, each triggered when the relevant conditions cross a threshold. It can also represent crises
with realistically "fat-tailed" severity (most are mild, a rare few are catastrophic, matching how
real crises and wars are distributed), and it computes early-warning indicators that rise before a
system approaches a tipping point.

**Limits.** The fat-tailed severity and the most extreme tipping behaviour are optional and explored
as uncertainty rather than baked into the headline. Crises are driven by thresholds and rules; they
capture the right qualitative behaviour but are not derived from a single fitted crisis dataset.

## 9. Finance and government debt

**What it does.** Government budgets, deficits, interest payments and debt are tracked with strict
accounting (every change in debt is matched by a corresponding flow, with no money appearing or
disappearing). Debt crises are resolved consistently with that accounting. There is also an optional
private-credit layer in which over-borrowing raises the cost of credit and damps the economy (a
"financial accelerator").

**Limits.** The government side is solid and accounting-consistent. The private-credit layer is a
first version: it tracks borrowing and its feedback on interest rates, but does not yet model the
full banking balance sheet (the matching deposits and money supply). That fuller version is a
planned next step.

## 10. Uncertainty and validation (how we keep it honest)

**What it does.** The model is not run only once. It is run as large ensembles with its parameters
drawn from evidence-based ranges, its sensitivity to each parameter is measured, and it is compared
against historical data and against simple "naive" forecasts. The rule throughout is that a
mechanism only counts if it is validated, and uncertain mechanisms are reported as ranges, not as
false precision.

**Limits.** The honest accuracy bar for multi-year forecasts is "does it beat a naive baseline",
because no credible global model reliably predicts the world years ahead. The model is built to be
*calibrated about its own uncertainty*, which is the realistic goal — not to be a crystal ball.

---

## One-line summary per layer

| Layer | Strength | Main limit |
|---|---|---|
| Economy | grounded to 2015–2023 history; capital–energy substitution | no full market clearing yet |
| Climate & carbon | matches mainstream science | feedbacks uncertain; not a full Earth-system model |
| Damage & cost of carbon | evidence-based, uncertainty carried | damages wide across the field |
| Resources | feeds prices→inflation | broad, rule-based prices |
| Society & politics | distinctive, responsive | no single dataset to calibrate against |
| Geopolitics | military power grounded in data; conflict risk has real skill | cannot predict specific wars |
| Culture | only load-bearing traits kept | links validated in sign only |
| Risk & crises | fat tails + early warning available | threshold/rule-based |
| Finance & debt | strict, consistent accounting | private banking not yet full |
| Uncertainty & validation | ensembles, sensitivity, backtests | beats naive baselines, not a crystal ball |
