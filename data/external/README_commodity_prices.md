# World Bank commodity price indices (annual, nominal)

`worldbank_commodity_price_indices_annual.csv` — 1990-2024, index 2010 = 100.

| column | Pink Sheet series |
|---|---|
| `energy_index_2010_100` | Energy |
| `food_index_2010_100` | Food (agriculture sub-index) |
| `metals_minerals_index_2010_100` | Metals & Minerals |

**Source.** World Bank Commodity Markets Outlook, "The Pink Sheet", historical annual data,
sheet `Annual Indices (Nominal)`, file stamped "Updated on January 03, 2025":
<https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Annual.xlsx>
Retrieved 2026-08-24. World Bank data is published under CC BY 4.0.

**What it is and is not.** These are *market price* indices for traded commodity baskets.
GIM's `global_state.prices` are *clearing* indices for three aggregate resources, normalised
to 1.0 in the base year, produced by a supply-demand rule with a reserve buffer and no
storage, futures or financialisation. The two constructs are related but not the same
quantity, so the defensible test is direction and multi-year magnitude, not year-by-year
timing. E13 is written on that basis and says so in its output.
