from __future__ import annotations

from dataclasses import dataclass

from . import calibration_params as cal


# Country-level macro priors for the 20-actor historical backtest surface.
# These values are coarse 2015-2022 averages anchored on the WDI23/OECD-style
# shares discussed in the calibration notes. Savings is handled more carefully
# than taxes/social spending: until the econometric pass lands, the legacy
# one-sector capital block only uses country savings as a downward correction to
# the world-average prior, avoiding mechanical over-acceleration in high-saving
# economies that the current production structure cannot yet absorb faithfully.


@dataclass(frozen=True)
class CountryMacroPrior:
    savings_rate: float
    tax_rate: float
    social_spend_share: float


COUNTRY_MACRO_PRIORS: dict[str, CountryMacroPrior] = {
    "Australia": CountryMacroPrior(savings_rate=0.24, tax_rate=0.29, social_spend_share=0.18),
    "Brazil": CountryMacroPrior(savings_rate=0.16, tax_rate=0.33, social_spend_share=0.25),
    "Canada": CountryMacroPrior(savings_rate=0.23, tax_rate=0.31, social_spend_share=0.18),
    "China": CountryMacroPrior(savings_rate=0.44, tax_rate=0.20, social_spend_share=0.10),
    "France": CountryMacroPrior(savings_rate=0.22, tax_rate=0.46, social_spend_share=0.31),
    "Germany": CountryMacroPrior(savings_rate=0.27, tax_rate=0.46, social_spend_share=0.26),
    "India": CountryMacroPrior(savings_rate=0.30, tax_rate=0.18, social_spend_share=0.08),
    "Indonesia": CountryMacroPrior(savings_rate=0.31, tax_rate=0.12, social_spend_share=0.07),
    "Italy": CountryMacroPrior(savings_rate=0.20, tax_rate=0.43, social_spend_share=0.28),
    "Japan": CountryMacroPrior(savings_rate=0.26, tax_rate=0.35, social_spend_share=0.24),
    "Mexico": CountryMacroPrior(savings_rate=0.22, tax_rate=0.17, social_spend_share=0.09),
    "Netherlands": CountryMacroPrior(savings_rate=0.28, tax_rate=0.39, social_spend_share=0.19),
    "Russia": CountryMacroPrior(savings_rate=0.28, tax_rate=0.35, social_spend_share=0.13),
    "Saudi Arabia": CountryMacroPrior(savings_rate=0.31, tax_rate=0.29, social_spend_share=0.12),
    "South Korea": CountryMacroPrior(savings_rate=0.34, tax_rate=0.27, social_spend_share=0.12),
    "Spain": CountryMacroPrior(savings_rate=0.22, tax_rate=0.38, social_spend_share=0.24),
    "Switzerland": CountryMacroPrior(savings_rate=0.33, tax_rate=0.27, social_spend_share=0.17),
    "Turkey": CountryMacroPrior(savings_rate=0.25, tax_rate=0.20, social_spend_share=0.13),
    "United Kingdom": CountryMacroPrior(savings_rate=0.15, tax_rate=0.33, social_spend_share=0.21),
    "United States": CountryMacroPrior(savings_rate=0.18, tax_rate=0.28, social_spend_share=0.19),
}


COUNTRY_NAME_ALIASES = {
    "Korea, Rep.": "South Korea",
    "Russian Federation": "Russia",
    "Saudi Arabia (Kingdom of)": "Saudi Arabia",
    "Turkiye": "Turkey",
    "UK": "United Kingdom",
    "USA": "United States",
}


def normalize_country_name(country_name: str) -> str:
    normalized = " ".join(country_name.split())
    return COUNTRY_NAME_ALIASES.get(normalized, normalized)


def get_country_macro_prior(country_name: str) -> CountryMacroPrior | None:
    return COUNTRY_MACRO_PRIORS.get(normalize_country_name(country_name))


def get_savings_rate(country_name: str) -> float:
    prior = get_country_macro_prior(country_name)
    if prior is None:
        return cal.SAVINGS_BASE
    return min(prior.savings_rate, cal.SAVINGS_BASE)


def get_tax_rate(country_name: str) -> float:
    prior = get_country_macro_prior(country_name)
    return prior.tax_rate if prior is not None else cal.TAX_RATE_BASE


def get_social_spend_share(country_name: str) -> float:
    prior = get_country_macro_prior(country_name)
    return prior.social_spend_share if prior is not None else cal.SOCIAL_SPEND_BASE
