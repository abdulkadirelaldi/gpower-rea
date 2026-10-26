"""Effect-size calculators, including the non-obvious pooling rule (E-007)."""

from __future__ import annotations

import math

import pytest

from gpower_rea import effectsize as es
from gpower_rea.procedures import ValidationError


def test_equal_n_option_uses_rms_not_pooled():
    """The 'n1 = n2' drawer uses sqrt((s1^2+s2^2)/2), which differs from the
    textbook pooled SD as soon as the group sizes differ."""
    out = es.d_two_independent_means(10.0, 8.0, sd1=2.0, sd2=6.0, equal_n=True)
    assert out["pooled_sd"] == pytest.approx(math.sqrt((4.0 + 36.0) / 2.0))
    assert out["effect_size"]["value"] == pytest.approx(2.0 / math.sqrt(20.0))
    assert "n1 = n2" in out["formula"]


def test_unequal_n_option_uses_weighted_pooling():
    out = es.d_two_independent_means(
        10.0, 8.0, sd1=2.0, sd2=6.0, equal_n=False, n1=10, n2=40
    )
    expected = math.sqrt((9 * 4.0 + 39 * 36.0) / 48.0)
    assert out["pooled_sd"] == pytest.approx(expected)


def test_the_two_pooling_options_differ():
    a = es.d_two_independent_means(1.0, 0.0, 2.0, 6.0, equal_n=True)
    b = es.d_two_independent_means(
        1.0, 0.0, 2.0, 6.0, equal_n=False, n1=10, n2=40
    )
    assert a["pooled_sd"] != pytest.approx(b["pooled_sd"], rel=1e-6)


def test_equal_sds_make_both_options_agree():
    a = es.d_two_independent_means(5.0, 3.0, 4.0, 4.0, equal_n=True)
    b = es.d_two_independent_means(
        5.0, 3.0, 4.0, 4.0, equal_n=False, n1=17, n2=31
    )
    assert a["pooled_sd"] == pytest.approx(b["pooled_sd"])
    assert a["effect_size"]["value"] == pytest.approx(0.5)


def test_unequal_n_requires_both_group_sizes():
    with pytest.raises(ValidationError):
        es.d_two_independent_means(1.0, 0.0, 1.0, 1.0, equal_n=False, n1=10)


def test_matched_pairs_from_marginals():
    out = es.dz_matched_pairs(10.0, 8.0, sd1=3.0, sd2=3.0, correlation=0.5)
    sd_diff = math.sqrt(9.0 + 9.0 - 2 * 0.5 * 9.0)
    assert out["sd_difference"] == pytest.approx(sd_diff)
    assert out["effect_size"]["value"] == pytest.approx(2.0 / sd_diff)


def test_matched_pairs_correlation_bounds():
    with pytest.raises(ValidationError):
        es.dz_matched_pairs(1.0, 0.0, 1.0, 1.0, correlation=1.0)


def test_higher_correlation_gives_larger_dz():
    prev = -1.0
    for rho in (-0.5, 0.0, 0.3, 0.6, 0.9):
        dz = es.dz_matched_pairs(2.0, 0.0, 3.0, 3.0, rho)["effect_size"]["value"]
        assert dz > prev
        prev = dz


def test_dz_from_difference():
    out = es.dz_from_difference(1.5, 3.0)
    assert out["effect_size"]["value"] == pytest.approx(0.5)


def test_one_sample():
    out = es.d_one_sample(mean=105.0, reference=100.0, sd=10.0)
    assert out["effect_size"]["value"] == pytest.approx(0.5)


@pytest.mark.parametrize(
    "r2,expected",
    [(0.0, 0.0), (0.02 / 1.02, pytest.approx(0.02, rel=1e-12)), (0.5, 1.0)],
)
def test_f2_from_r_squared(r2, expected):
    assert es.f2_from_r_squared(r2)["effect_size"]["value"] == expected


def test_f2_rejects_r2_of_one():
    with pytest.raises(ValidationError):
        es.f2_from_r_squared(1.0)


def test_r_from_d_balanced_round_trips():
    for d in (0.2, 0.5, 1.0, 2.0):
        r = es.r_from_d_balanced(d)["effect_size"]["value"]
        back = 2.0 * r / math.sqrt(1.0 - r * r)
        assert back == pytest.approx(d, rel=1e-12)


def test_zero_or_negative_sd_rejected():
    for bad in (0.0, -1.0):
        with pytest.raises(ValidationError):
            es.d_one_sample(1.0, 0.0, bad)


def test_every_calculator_names_a_real_test():
    from gpower_rea.procedures import PROCEDURES

    samples = {
        "d-two-independent-means": dict(mean1=1, mean2=0, sd1=1, sd2=1),
        "dz-matched-pairs": dict(mean1=1, mean2=0, sd1=1, sd2=1, correlation=0.5),
        "dz-from-difference": dict(mean_difference=1, sd_difference=2),
        "d-one-sample": dict(mean=1, reference=0, sd=2),
        "f2-from-r-squared": dict(r_squared=0.1),
        "f2-from-partial-r-squared": dict(partial_r_squared=0.1),
        "r-from-d-balanced": dict(d=0.5),
    }
    assert set(samples) == set(es.CALCULATORS)
    for name, kwargs in samples.items():
        out = es.CALCULATORS[name](**kwargs)
        assert out["for_test"] in PROCEDURES
        assert out["effect_size"]["name"] in (
            "d", "dz", "r", "f2",
        )
