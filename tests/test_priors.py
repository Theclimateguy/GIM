"""Tests for the literature-grounded parameter priors (Phase 1-B)."""

import random
import statistics
import unittest

from gim.core.params import ParameterSet, default_params
from gim.core.priors import (
    Prior,
    all_priors,
    key_priors,
    sample_overrides,
    sample_parameter_set,
)

_VALID_DISTS = {"normal", "lognormal", "triangular", "uniform", "fixed"}


def _percentile(sorted_values, p):
    return sorted_values[min(len(sorted_values) - 1, int(p * len(sorted_values)))]


class KeyPriorSpecTests(unittest.TestCase):
    def setUp(self):
        self.kp = key_priors()

    def test_key_priors_loaded(self):
        self.assertGreaterEqual(len(self.kp), 15)
        self.assertIn("ECS_DEFAULT", self.kp)
        self.assertIn("DAMAGE_QUAD_COEFF", self.kp)

    def test_every_key_prior_is_well_formed_and_sourced(self):
        base = default_params()
        for name, prior in self.kp.items():
            self.assertIn(prior.dist, _VALID_DISTS, name)
            self.assertLess(prior.low, prior.high, name)
            self.assertTrue(prior.source.strip(), f"{name} missing source citation")
            self.assertIn(name, base, f"{name} is not a real model parameter")

    def test_samples_respect_bounds(self):
        rng = random.Random(7)
        for name, prior in self.kp.items():
            for _ in range(200):
                x = prior.sample(rng)
                self.assertGreaterEqual(x, prior.low, name)
                self.assertLessEqual(x, prior.high, name)


class LiteratureCalibrationTests(unittest.TestCase):
    """The priors must reproduce the published central estimates and ranges."""

    def setUp(self):
        self.kp = key_priors()

    def test_ecs_matches_ipcc_ar6(self):
        rng = random.Random(1)
        s = sorted(self.kp["ECS_DEFAULT"].sample(rng) for _ in range(8000))
        median = statistics.median(s)
        self.assertAlmostEqual(median, 3.0, delta=0.15)  # AR6 best estimate 3.0C
        # AR6 likely range 2.5-4.0 must sit inside the 5-95% interval
        self.assertLess(_percentile(s, 0.05), 2.5)
        self.assertGreater(_percentile(s, 0.95), 4.0)
        # very-likely range ~2-5
        self.assertGreater(_percentile(s, 0.05), 1.7)
        self.assertLess(_percentile(s, 0.95), 5.3)

    def test_damage_coefficient_spans_dice_to_howard_sterner(self):
        rng = random.Random(2)
        s = sorted(self.kp["DAMAGE_QUAD_COEFF"].sample(rng) for _ in range(8000))
        # DICE-2016R2 = 0.00236 is a low-end estimate: within support and in the lower tail.
        self.assertLessEqual(self.kp["DAMAGE_QUAD_COEFF"].low, 0.00236)
        self.assertGreaterEqual(_percentile(s, 0.10), 0.00236)
        # Howard-Sterner ~0.008 is reachable and sits above the median (a high-end estimate).
        self.assertLess(0.008, _percentile(s, 0.95))
        self.assertGreater(0.008, statistics.median(s))
        # median near the model's calibrated 0.006 (between DICE and HS)
        self.assertAlmostEqual(statistics.median(s), 0.006, delta=0.0015)

    def test_capital_share_in_pwt_gollin_band(self):
        p = self.kp["ALPHA_CAPITAL"]
        self.assertGreaterEqual(p.low, 0.2)   # capital share lower bound
        self.assertLessEqual(p.high, 0.42)    # ~1 - labor share (Gollin 0.65-0.80)


class LongTailAndSamplingTests(unittest.TestCase):
    def test_all_priors_cover_scalars_and_skip_vectors(self):
        ap = all_priors()
        # carbon-pool vectors must NOT be sampled
        self.assertNotIn("CARBON_POOL_FRACTIONS", ap)
        self.assertNotIn("CARBON_POOL_TIMESCALES", ap)
        # structural MAX/MIN/CAP/FLOOR limits excluded from the long tail
        self.assertFalse(any(k.endswith(("_MAX", "_MIN", "_CAP", "_FLOOR")) and k not in key_priors()
                             for k in ap))
        self.assertGreater(len(ap), len(key_priors()))

    def test_sampling_is_deterministic(self):
        kp = key_priors()
        a = sample_overrides(kp, random.Random(123))
        b = sample_overrides(kp, random.Random(123))
        self.assertEqual(a, b)
        c = sample_overrides(kp, random.Random(124))
        self.assertNotEqual(a, c)

    def test_sample_parameter_set_returns_valid_set(self):
        base = default_params()
        ps = sample_parameter_set(base, key_priors(), random.Random(5))
        self.assertIsInstance(ps, ParameterSet)
        self.assertEqual(len(ps), len(base))  # full parameter vector
        # sampled key value differs from default with overwhelming probability
        self.assertNotAlmostEqual(ps.ECS_DEFAULT, base.ECS_DEFAULT, places=6)

    def test_names_filter_restricts_sampled_keys(self):
        kp = key_priors()
        out = sample_overrides(kp, random.Random(0), names=["ECS_DEFAULT"])
        self.assertEqual(set(out), {"ECS_DEFAULT"})


if __name__ == "__main__":
    unittest.main()
