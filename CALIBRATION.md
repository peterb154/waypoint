# Calibration Learnings — Lodging & Food Judgment Layer

Living log of real towns/motels used to tune the judgment prompt. Each entry
is ground truth from Brian's actual experience or research, paired with what
the review data showed, paired with the rule it implies. Add to this file
as new towns get checked — don't let it go stale.

---

## REJECT — 1st Inn Alliance, Alliance, NE

**Verdict:** Independent, clears a ratings bar, but Brian's nose said no —
"zero charm... looked like a week to week rental. Not my scene."

**What the reviews showed:** Price-as-apology language is the tell.
> "Yes, you can pay $119 for a better name, but sometimes the most basic
> and simple is sufficient... We could have spent more, but because Arlene
> was so personable and helpful, she helped sell the room."

A fellow Tripadvisor tip-writer separately warned other travelers: "pick
one somewhere else or see if they have newly remodeled, but I doubt it."

**Rule:** Distinguish *price-as-apology* (reviewer is justifying why they
settled, comparing unfavorably to what they could've gotten) from
*price-as-value* (reviewer is delighted at what they got for the money).
"You CAN pay more for better" = apology. "Best stay for the price, full
stop" = value. Same vocabulary (price, $, "for the money"), opposite
meaning — this can't be a keyword filter, it needs the judgment layer
reading stance, not just topic.

---

## PASS — Covered Wagon Motel, Lusk, WY

**Verdict:** Brian's favorite of the Lusk options — "the place I thought
was perfect."

**What the reviews showed:** Consistent unqualified, sensory, repeat-visit
language across multiple reviews:
> "What a wonderful little motel!... We were surprised to return and find
> our room had been cleaned and our towels replaced, we have not stayed
> anywhere with maid service since the beginning of Covid."

One review was business-travel-coded ("excellent place for inbound non-
touristy Wyoming necessities") and Claude initially over-weighted that
single review as a caution flag. It was wrong to — the review was still
unambiguously positive, just from a different traveler type.

**Rule:** Don't let one outlier-flavored review (e.g. mentions "business")
override a cluster of consistent, specific, sensory, repeat-visit reviews.
Weigh preponderance, not the presence of any single flagged word. A motel
serving both leisure and business travelers well is evidence of being
well-run, not evidence of being generic.

**Also confirmed:** Lusk passes on food but thinly — one real sit-down
option (Silver Dollar Bar and Grill) plus a Subway. "Both bars clear"
rule should pass this, but it's a near-thing, not a slam dunk. Town-level
food strength is a spectrum, not just pass/fail.

---

## PASS — Mountain Spirit Inn, Darby, MT

**Verdict:** "What a cool little place that was."

**What the reviews showed:** The strongest single signal of all four
towns so far — the *owner's own review responses* are personal, specific,
and funny, not templated:
> Guest: "...a real gem in Darby." Owner (Adele) reply: "Regarding gems,
> the Mountain Spirit Inn is gem. However, you can find real gems at
> Crystal Mountain... and also at Gem Mountain along the Skalkaho Pass,
> which is a business where you can pan for Sapphires."

Also: owner mailed a forgotten hat and a forgotten pillow back to guests
at no charge, unprompted, more than once (different guests, different
trips) — a repeated pattern, not a one-off.

**Rule:** Owner-responds-to-reviews is a strong, *structurally available*
signal (Places data shows whether/how a business replies). Template
replies ("Thank you for your feedback!") are neutral-to-weak. Specific,
personality-laden, individualized replies are a strong positive — often
stronger than guest review text itself, because it's the owner's own
unfiltered voice.

**Caution surfaced:** Listing mentioned "extended stay/weekly rates" —
structurally identical to the Alliance red flag. But context made it a
non-issue: it was one listed amenity among overwhelmingly leisure-
traveler reviews (skiers, hunters, road-trippers), not the dominant use
case. **"Offers weekly rates" alone is not the tell. "Weekly rates is the
dominant pattern in actual reviews" is.** Same structural fact, opposite
meaning depending on what the review corpus actually shows — this is
why it has to be a judgment call on the whole picture, not a rule on a
single field.

---

## PASS — Georgetown Mountain Inn, Georgetown, CO

**Verdict:** Loved it.

**What the reviews showed:** Larger, more conventional operation (33
rooms, 2 stories, pool/hot tub) than the other three — reads as "well-run
small hotel" more than "owner's personality is the whole place." Reviews
skew toward competent-and-consistent rather than personality-driven:
"friendly and helpful staff, comfortable, clean rooms" — genuinely the
most generic-sounding praise of the four. A couple of minor gripes
showed up too (dusty cabinets, a cold room one morning, one review
mentioning a torn box spring under the bed) — nothing disqualifying.

**Food-proximity signal, explicit in reviews:**
> "It is well within walking distance to tasty food..."
> "The next door restaurant/bar fit in great with my way of travel."
> "...our favorite restaurant Coopers on The Creek!"

**Rule (Brian's explicit framing):** *"Nice restaurants don't usually
exist next to a hell hole drug den."* Food quality and proximity isn't
just a separate checklist item to verify alongside lodging — it's
corroborating evidence about the town/block itself. A good named,
specifically-loved restaurant mentioned unprompted in a motel's own
reviews is a signal about the surrounding area, not just about dinner.
Weigh it as such.

**Also confirmed:** A motel doesn't need to be tiny or owner-personality-
driven to pass. "Competent, well-run, real town, good food nearby" is a
valid pass even without an Adele. Don't over-index Phase 1 calibration
toward only rewarding the most charming/personal cases — Georgetown shows
the bar admits solid-but-unspectacular too, as long as the fundamentals
(independent, clean, good food nearby, no major complaints) hold.

---

## PASS (with texture) — Hotel Seville, Harrison, AR

**Verdict:** Brian loves it. Notable: this is the first entry that's not a
motel at all — a 55-room, 1929-era full-service historic hotel with a bar
and restaurant, soft-branded as part of Choice Hotels' "Ascend Hotel
Collection."

**New wrinkle — soft brands aren't the same as flagged brands.** "Ascend
Hotel Collection" is Choice's affiliation tier for independently owned,
individually-named historic/boutique properties — they keep their own
identity and character but tap into a chain's booking/loyalty system. A
flat blocklist match on "Choice Hotels" or "Ascend" would wrongly kill
this one. **Rule: the blocklist needs a soft-brand exception list**
(Ascend Hotel Collection, Tapestry Collection by Hilton, Tribute Portfolio
by Marriott, Curio Collection by Hilton, Autograph Collection — these are
explicitly "independent character, chain-affiliated" tiers) distinct from
flagged full chain brands (Quality Inn, Comfort Inn, Holiday Inn Express,
etc., which are also technically Choice/IHG but are standardized,
interchangeable builds).

**What the reviews showed — best example yet of "good but uneven," not
flawless:**

Strong, specific, can't-be-faked praise:
> "Bar and restaurant on site with excellent food and a very friendly
> bartender. Centrally located to some of the best riding in Arkansas and
> Missouri." (unprompted moto-relevant detail — high-value signal)

Real, clustered, legitimately negative reviews sitting right next to it:
> "room was directly over the bar so we didn't get any sleep until after
> midnight. The hotel over promises and under performs."
> "First, the restaurant is a joke. Basically hotdogs and chili. Then,
> something went wrong with the water system and the water was cut off,
> without explanation, for about an hour."
> "The walls are paper thin so we could hear everything going on the next
> room."

Multiple independent reviewers converge on the same complaint pattern
("could have been nice but...", "over promises and under performs") —
old building, mid-renovation, restaurant under separate sub-let
management so quality is inconsistent and disconnected from the hotel's
own management.

**Rule:** This is a different failure-adjacent pattern than anything else
logged so far — not fake/generic (Alliance), not an outlier review to
discount (Lusk). It's **a real, charming, worth-it place with genuine
inconsistency**, openly acknowledged by multiple reviewers in similar
language. Don't auto-penalize a cluster of specific operational
complaints (noise, an under-construction feel, a so-so sub-let
restaurant) the way a cluster of *generic* complaints should be
penalized. The texture is: complaints are specific, varied in topic, and
sit alongside equally specific praise — that combination reads as "real
old building with real character and real flaws," which is a pass, not
a borderline case. A town/property log should be able to say "great, but
ask for a room not over the bar" — that's a usable verdict, not a wishy-
washy one.

**Food note:** Restaurant-on-site quality is explicitly inconsistent here
(excellent per one review, "basically hotdogs and chili" per another) —
this is a case where the *hotel* passes clearly but the on-site food
specifically should not be the sole food signal for the town. Worth
checking Harrison's separate food options rather than resting on the
hotel's own restaurant.

## Running rule set (cumulative, plain-language)

1. **Price-as-apology vs. price-as-value.** Read the stance, not just
   whether price is mentioned.
2. **Preponderance over outliers.** One oddly-flavored review shouldn't
   override a cluster of consistent positive ones.
3. **Owner review-response quality is a strong, cheap, structural signal.**
   Specific > templated. Look at it as seriously as guest review text.
4. **Structural facts (e.g. "weekly rates offered") need context, not a
   blanket penalty.** Ask whether it's the dominant use case in the
   reviews or a side option.
5. **Food proximity corroborates the town/block, not just dinner plans.**
   A good, specifically-named restaurant mentioned inside a motel's own
   reviews is evidence about the surrounding area's character.
6. **The bar isn't "must be charming/personality-driven."** Competent and
   well-run, in a real town, with food nearby and no major complaints, is
   a legitimate pass even without an owner-personality angle.
7. **Soft chain brands (Ascend, Tapestry, Tribute Portfolio, Curio,
   Autograph Collection) are not the same as flagged chain brands.** They
   affiliate independently-named/run historic or boutique properties with
   a booking system. Blocklist needs to whitelist these explicitly rather
   than matching on the parent company name.
8. **Specific, varied, real complaints sitting next to specific, real
   praise = an honest "good but uneven" pass, not a red flag.** This is
   different from generic complaints (weak signal either way) and
   different from a single outlier review (rule 2). Multiple reviewers
   independently converging on the same specific gripe (e.g. "room over
   the bar," "restaurant under separate management is hit or miss") is
   useful, actionable detail to surface in the verdict, not a reason to
   fail the town.
9. **Lodging type matters — a rider wouldn't book a B&B.** The ideal is an
   independent motel or a classic independent hotel/lodge/inn. A bed &
   breakfast, guest house, private room, or single-cabin rental is not
   typical motorcycle-trip lodging. If a town's best independent option is
   one of those, cap its independence/character score (0.75 max) and don't
   let it carry the town to route-worthy on lodging alone.
10. **Town charm is its own dimension — measure KIND, not count.** A
    walkable historic downtown, a real arts/festival culture, or a genuine
    recreation destination is charm. A single famous roadside oddity (a big
    sculpture, one museum) in an otherwise workforce/railroad/industrial
    town is NOT charm — attraction *count* doesn't separate the two
    (Alliance NE has Carhenge + museums yet zero downtown character). Lean
    on the model's own knowledge of the town plus review mentions of
    "historic downtown / main street / festival," with the attractions list
    as context only.
11. **Food: judge DINNER, and destination vs. eat-fine.** Score for a rider
    arriving in the evening wanting dinner. A "scene" that's mostly coffee /
    ice-cream / bakery / deli / daytime-only spots is LIMITED (1.0), not a
    food town. Reserve the full 2.0 for a genuine *destination* — the best
    non-chain dinner spot rating ~4.7+ (or unmistakably raved about); a
    normal small town with real restaurants topping out at 4.4–4.6 is 1.5
    ("you'll eat fine"). Review COUNT is a red herring — a small town funnels
    all its reviews to the one main spot, so a 4.5 bar & grill with 800+
    reviews is still 1.5. (Wamego 1.5 vs Georgetown/Valentine 2.0.)
12. **Select the best SUITABLE lodging, don't just cap the top-rated.** Pick
    the best motel/hotel/inn as the town's representative even if a B&B or
    lodge outranks it — the rider books the motel. Only fall back to a B&B
    (and apply the 0.75 cap) when nothing suitable exists. (Wamego: score the
    independent hotel, not the higher-rated Victory Inn B&B.)
13. **Lodging is a GATE, not just a slice.** The tool finds places to SLEEP
    and eat. A town with NO bookable rider lodging (only vacation rentals /
    lofts / hunting-package lodges / nothing) is not an overnight candidate,
    period — cap it near-zero (total 1.5, filter-out) no matter how good the
    food or charm. A weak or B&B-only town still *counts* as lodging; the
    gate is only for zero bookable lodging. (St. Marys KS, Dallas SD.)

## Reject hunt — "can it say no?" (2026-07-05, `scripts/reject_hunt.py`)

Batched a real I-80 corridor (NE→WY, 20 towns, not cherry-picked), ranked
ascending by weakest best-independent-lodging. The band range came out fully
populated, so the "still no FAIL observed" open item is closed — the tool
reliably says no.

- **13/20 filter-out**, mostly via the **lodging gate** (only vacation rentals /
  Airbnb / event venues → no bookable rider bed).
- **Healthy gradient above the gate:** Cozad 4.5 / Big Springs 5.0 / Lexington 5.5
  (marginal) → Ogallala 7.0 (acceptable) → Gothenburg / Sidney / Kimball 8.0
  (route-worthy). Weak-but-real motels get graded down without being zeroed.
- **Spot-checked the tail for false negatives — none.** Maxwell is a genuine
  FAIL (search found 1 unrated "Cabins", 0 chains dropped, 0 food — nothing to
  miss). Paxton's only "lodging" is a wedding venue → gate.

**Mode-gate learning (confirmed, not a bug):** several moto-mode FAILs are
B&B/Airbnb-only towns that correctly PASS in `--couple`. Potter NE gates in moto
(1912 boarding house) but scores **8.5 route-worthy** for a couple; Gibbon NE
gates in moto (Airbnb house) but scores **7.0** for a couple. The gate is
mode-appropriate — it rejects intimate lodging *for a group of riders*, not
categorically. (Gibbon's couple-mode lodging also earned only review_quality
0.5 on a 5.0★/2-review Airbnb — the skew/volume tempering doing its job.)

## Still needed
- **Reject variety: well covered.** Failure modes confirmed — workforce/no-charm
  (Alliance NE 3.5), no-bookable-lodging hunting town (Dallas SD 1.5),
  destination-food-but-no-bed (St. Marys KS 1.5), dead nothing-town (Maxwell NE
  0.0), and wedding-venue-as-lodging (Paxton NE 0.0). Still worth finding: a town
  that scores fine on lodging + charm but has genuinely *dead food*, and a
  tourist-trap that's all chains behind a charming facade.

---

## Composite Scoring Model v2 (LIVE — matches verdict.py)

Output: a score from 0–10. Scored on the town's best SUITABLE independent
lodging plus the town's food and character. Weights: Lodging 4 / Food 3 /
Town 3.

### Lodging (4 pts)

**Independence & Character (0–2)**
- 2 — Clearly independent motel/hotel/inn, character evident in reviews (named owner, specific decor, personality-driven praise)
- 1 — Independent but generic execution, OR soft-brand affiliated (Ascend, Tapestry, Tribute Portfolio, Curio, Autograph, Unbound)
- 0 — Chain (blocklist hit, excluding soft-brand exceptions)
- **B&B RULE:** if the best option is a bed & breakfast / guest house / private room / single cabin, cap this at **0.75** — a rider wouldn't normally book one, and a town whose only good lodging is a B&B can't be route-worthy on lodging.

**Price Tier (0–1)**
- 1 — No price-apologetics; price unmentioned or a pleasant surprise for the value
- 0.5 — Mixed
- 0 — Price-as-apology dominant ("decent for the money," "you can pay more for better," "budget option but")

**Review Quality (0–1)**
- 1 — Specific, sensory, repeat-visit; complaints (if any) specific and offset by specific praise
- 0.5 — Positive-but-generic, OR good-but-uneven (real praise beside real clustered complaints — don't auto-fail)
- 0 — Thin, generic, or dominant complaint pattern

### Lodging GATE

Before scoring, check for bookable rider lodging. If the town has NO suitable
motel/hotel/inn/lodge worth a look — only vacation rentals, private lofts,
hunting-package lodges, or nothing — set all lodging scores to 0 and cap the
**total at 1.5 (filter-out)**, regardless of food or charm. A weak or B&B-only
town still counts (see B&B RULE); the gate is only for *zero* bookable lodging.
Selection: pick the best *suitable* option (motel/hotel/inn) as representative
even if a B&B/lodge outranks it; only fall to a B&B (0.75 cap) when nothing
suitable exists.

### Food (3 pts)

**Proximity & Quality (0–2)** — judge an evening DINNER arrival
- 2 — A genuine non-chain *destination*: best dinner spot ~4.7+ or unmistakably raved about (count alone doesn't qualify)
- 1.5 — Solid real dinner options (bar & grill / Mexican / diner / BBQ, ~4.4–4.6) — you'll eat fine, not a destination. DEFAULT for a normal small town.
- 1.0 — LIMITED: mostly coffee / bakery / ice-cream / deli or daytime-only spots, or a single weak option
- 0 — Chain-only or dead food scene

**Recency (0–1)**
- 1 — Strong reviews within ~18 months
- 0.5 — Older or mixed recency
- 0 — No recent signal or evidence of closure

### Town (3 pts)

**Town Charm (0–2)** — measure KIND, not count (see rule 10)
- 2 — Charming: walkable historic downtown, real arts/festival culture, or a genuine recreation destination
- 1 — Some draw but ordinary
- 0 — Workforce/industrial/transit town with no real center (one famous roadside oddity does NOT count)

**Riding Context (0–1)**
- 1 — On/near known good riding; reviews mention riding or outdoor recreation unprompted
- 0.5 — General outdoor/tourism, no specific riding signal
- 0 — Pure transit or freight town

---

## Town Scores (live model, 2026-07-01)

Dimensions: Ind = Independence/Character (2), Prc = Price (1), Rev = Review
Quality (1), Food (2), Rec = Recency (1), Chrm = Charm (2), Rid = Riding (1).

| Town | Ind | Prc | Rev | Food | Rec | Chrm | Rid | Total | Band | Lodging scored |
|---|---|---|---|---|---|---|---|---|---|---|
| Georgetown, CO | 2 | 1 | 1 | 2 | 1 | 2 | 1 | **10.0** | route-worthy | Clear Creek Inn |
| Red Lodge, MT | 2 | 1 | 1 | 2 | 1 | 2 | 1 | **10.0** | route-worthy | The Pollard Hotel |
| Darby, MT | 2 | 1 | 1 | 2 | 1 | 1.5 | 1 | **9.5** | route-worthy | Darmont Hotel |
| Valentine, NE | 2 | 1 | 1 | 2 | 1 | 1.5 | 1 | **9.5** | route-worthy | Trade Winds Motel |
| Crawford, NE | 2 | 1 | 1 | 1.5 | 1 | 2 | 1 | **9.5** | route-worthy | Hilltop Motel |
| Lusk, WY | 2 | 1 | 1 | 1.5 | 1 | 1 | 0.5 | **8.0** | route-worthy | Covered Wagon Motel |
| Wamego, KS | 1 | 0.5 | 0.5 | 1.5 | 1 | 1.5 | 0.5 | **6.5** | acceptable | Wamego Inn & Suites |
| Harrison, AR | 1 | 0.5 | 0.5 | 1.5 | 1 | 1 | 0.5 | **6.0** | acceptable | Hotel Seville |
| Alliance, NE | 1 | 0 | 0.5 | 1 | 1 | 0 | 0 | **3.5** | filter-out | Rainbow Motel |
| Dallas, SD | 0 | 0 | 0 | (1.5) | 1 | (0) | 0 | **1.5** | filter-out | GATE — hunting lodges, no bed |
| St. Marys, KS | 0 | 0 | 0 | (2) | 1 | (1.5) | 0.5 | **1.5** | filter-out | GATE — vacation rentals only |
| Maxwell, NE | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0.0** | filter-out | true FAIL — 1 unrated "Cabins", 0 food |
| Paxton, NE | 0 | 0 | 0 | (1.5) | 1 | (1) | 0.5 | **0.0** | filter-out | GATE — Hanging H is a wedding venue |

Notes:
- The tool scores the town's best *found* suitable lodging, which may differ from
  a specific property Brian had in mind (e.g. Georgetown on Clear Creek Inn).
  Relative ordering and bands are what matter.
- Dallas / St. Marys hit the **lodging gate**: parenthesized food/charm are their
  raw dimension reads, but with no bookable bed the total is capped at 1.5.
- Expect ~±0.5 run-to-run jitter on mid towns (LLM temperature 0.2); bands are stable.

**Score interpretation:**
- 8–10: Route-worthy — build a day around this town
- 6–7.99: Acceptable — good stop if the corridor goes there
- 4–5.99: Marginal — surface with a warning, let the human decide
- <4: Filter out
