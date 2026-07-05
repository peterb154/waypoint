"""Pins nearest-town venue attribution (area._nearest_filter).

The bug this guards: a small town (Louisville, KS) borrowed a bigger neighbour's
(Wamego, KS) motels/restaurants/attractions because both radius searches overlap.
Attribution credits each venue only to its nearest reference town.
"""

from __future__ import annotations

import area

# Roughly the real geography: Louisville and Wamego, KS, ~5 mi apart.
LOUISVILLE = ("Louisville, KS", 39.2506, -96.3161)
WAMEGO = ("Wamego, KS", 39.2019, -96.3050)
ANCHORS = [LOUISVILLE, WAMEGO]

# A Wamego landmark (the Oz Museum sits on Wamego's Lincoln Ave).
OZ_MUSEUM = (39.2016, -96.3047)


def test_venue_credited_to_nearest_town():
    keep_wamego = area._nearest_filter(*WAMEGO, ANCHORS)
    keep_louisville = area._nearest_filter(*LOUISVILLE, ANCHORS)
    assert keep_wamego(*OZ_MUSEUM) is True
    assert keep_louisville(*OZ_MUSEUM) is False


def test_town_is_always_an_anchor_even_if_omitted():
    # A town not present in the anchor list must still be able to keep its own venues.
    keep = area._nearest_filter("Louisville, KS", 39.2506, -96.3161, [WAMEGO])
    # A point right at Louisville's center is nearest to Louisville, not Wamego.
    assert keep(39.2506, -96.3161) is True


def test_no_anchors_disables_filtering():
    assert area._nearest_filter("Anywhere, KS", 39.0, -96.0, None) is None
    assert area._nearest_filter("Anywhere, KS", 39.0, -96.0, []) is None
