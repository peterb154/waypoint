"""Pins the volume-aware ranking tuning (places.weighted_rating).

The whole point is that a tiny-sample gem must not bury a high-review classic in
the top-N cutoff — while a genuine small-town gem is still only nudged, not
buried. If someone retunes RATING_PRIOR / RATING_CONFIDENCE, these say what broke.
"""

from __future__ import annotations

import places


def rank(cands):
    """Same key _gather uses, applied to (rating, reviews) tuples."""
    keyed = [(places.weighted_rating(r, n), n or 0, (r, n)) for r, n in cands]
    keyed.sort(key=lambda k: (k[0], k[1]), reverse=True)
    return [k[2] for k in keyed]


def test_high_volume_classic_beats_tiny_sample_gem():
    # The motivating case: a 4.4★/682 hotel must outrank a 5.0★/8 cabin.
    order = rank([(5.0, 8), (4.4, 682)])
    assert order[0] == (4.4, 682)


def test_small_town_gem_stays_competitive():
    # A real 4.9★/30 gem must still beat a generic 4.2★/150 motel — the shrinkage
    # discounts uncertainty, it does not impose a review floor.
    order = rank([(4.9, 30), (4.2, 150)])
    assert order[0] == (4.9, 30)


def test_missing_data_sorts_last():
    order = rank([(4.5, 40), (None, None), (0.0, 0)])
    assert order[0] == (4.5, 40)
    assert order[-1] in {(None, None), (0.0, 0)}


def test_more_reviews_breaks_ties_at_equal_rating():
    order = rank([(4.5, 20), (4.5, 400)])
    assert order[0] == (4.5, 400)
