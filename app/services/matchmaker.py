"""Matchmaking algorithm for FightHub.

Produces a compatibility score between two fighters by combining
nine weighted factors. ELO is computed fresh from fight history on every call.
"""

from __future__ import annotations
from datetime import date as _date, timedelta as _timedelta
from typing import List

# ── ELO configuration ──────────────────────────────────────────────────────

elo_start           = 0
elo_min             = -200
elo_k               = 24

# Loss scaling: (actual - expected) is already negative for a loss, so the
# natural ELO formula gives ~-12 vs equal opponent.  The dampening scales that
# down so losses land at the intended levels:
#   vs equal   (expected ≈ 0.5)  → 24 × 0.50 × 0.5  = -6
#   vs stronger (expected ≈ 0.25) → 24 × 0.50 × 0.25 = -3
#   vs weaker   (expected ≈ 0.75) → 24 × 0.50 × 0.75 = -9
loss_dampening      = 0.50

# Season engagement incentives
participation_bonus  = 1.5   # flat ELO gain per fight, win or lose
activity_threshold   = 3     # fights in last 180 days to be "active in season"
activity_bonus_mult  = 1.15  # win gains 15 % more for active-season fighters
upset_elo_gap        = 150   # opponent must be this many ELO points higher …
upset_bonus_mult     = 1.20  # … to earn a 20 % upset bonus on a win

ELO_BAND_NAMES = ["Amateur", "Prospect", "Contender", "Regional", "Elite"]


def elo_band(elo: float) -> str:
    idx = max(0, int(elo // 200))
    return ELO_BAND_NAMES[min(idx, len(ELO_BAND_NAMES) - 1)]


method_multiplier = {
    "ko": 1.5,
    "tko": 1.5,
    "submission": 1.3,
    "decision": 1.0,
    "disqualification": 0.0,
}


def _method_multiplier(method) -> float:
    if not isinstance(method, str):
        return 1.0
    return method_multiplier.get(method.lower().strip(), 1.0)


# ── factor weights (must sum to 1.0) ───────────────────────────────────────

weight_W       = 0.20
elo_w          = 0.18
record_w       = 0.12
form_w         = 0.12
method_W       = 0.10
opp_quality_w  = 0.10
experience_w   = 0.10
recent_form_w  = 0.05
age_w          = 0.03

_weight_sum = (weight_W + elo_w + record_w + form_w + method_W +
               opp_quality_w + experience_w + recent_form_w + age_w)
if abs(_weight_sum - 1.0) >= 1e-9:
    raise ValueError(f"Factor weights must sum to 1.0, got {_weight_sum}")


# ── cross-sport experience transfer ──────────────────────────────────────

# How much of a fighter's record in one discipline counts as relevant
# experience in another. These are judgement calls about shared skills — stance,
# range, striking defence, ring craft, having been hit hard by a stranger — and
# they are deliberately asymmetric: a boxer's hands carry a long way into
# kickboxing, a kickboxer's hands carry less far into pure boxing. Same sport is
# always 1.0. Tune these first if matchmaking starts producing mismatches.
sport_transfer = {
    ("boxing",     "kickboxing"): 0.60,
    ("boxing",     "muaythai"):   0.50,
    ("boxing",     "mma"):        0.35,
    ("kickboxing", "boxing"):     0.45,
    ("kickboxing", "muaythai"):   0.80,
    ("kickboxing", "mma"):        0.50,
    ("muaythai",   "boxing"):     0.40,
    ("muaythai",   "kickboxing"): 0.80,
    ("muaythai",   "mma"):        0.50,
    ("mma",        "boxing"):     0.35,
    ("mma",        "kickboxing"): 0.45,
    ("mma",        "muaythai"):   0.45,
}
default_transfer = 0.30   # unrecognised discipline: some credit, not much

# Every discipline the transfer matrix knows about. Prior experience may be
# declared in any of these, whether or not the platform runs it as a sport yet.
transfer_sports = tuple(sorted({s for pair in sport_transfer for s in pair}))

# Transferred credit goes stale on a half-life, but never expires completely —
# a decade-old record still means you have been in there before.
transfer_halflife_days = 730
transfer_floor         = 0.25

# What transfers: bout count, record and rating. What does not: finish rate,
# recent form and opponent quality. How you finish fights and how sharp you are
# right now are the most discipline-specific things we measure, so those factors
# stay native rather than being imported from another sport's history.

# ── debut protection ─────────────────────────────────────────────────

# A weighted average can still rank a bad pairing highly when the other factors
# happen to line up, so an experience mismatch is enforced as a filter rather
# than left to the weights to express. The tolerated gap scales with experience:
# a debutant against a 4-bout fighter is a mismatch, a 12-bout fighter against a
# 16-bout fighter is not.
debut_experience_epsilon = 0.5   # effective bouts below this is a true debut
debut_max_opponent_bouts = 1.5   # the most a true debutant may be matched with
experience_ratio_limit   = 2.0   # otherwise: opponent may have this many times …
experience_gap_allowance = 2.0   # … your bouts, plus this many


def transfer_coefficient(from_sport: str, to_sport: str) -> float:
    if from_sport == to_sport:
        return 1.0
    return sport_transfer.get((from_sport, to_sport), default_transfer)


def _transfer_decay(last_bout_date: str | None, as_of: str | None = None) -> float:
    """Recency multiplier on transferred credit.

    An unknown last-bout date returns full credit on purpose. Over-crediting
    experience only steers a fighter towards tougher opponents, which is the
    safe direction to be wrong in; under-crediting is what puts a seasoned
    fighter across from a novice.
    """
    if not last_bout_date:
        return 1.0
    try:
        last  = _date.fromisoformat(str(last_bout_date)[:10])
        pivot = _date.fromisoformat(as_of) if as_of else _date.today()
    except (ValueError, TypeError):
        return 1.0
    days = (pivot - last).days
    if days <= 0:
        return 1.0
    return max(transfer_floor, 0.5 ** (days / transfer_halflife_days))


def experience_credit(
    sources: list[dict],
    to_sport: str,
    as_of: str | None = None,
) -> dict:
    """Fold a fighter's record in other disciplines into credit towards this one.

    Each source is {sport, wins, losses, draws, elo, last_bout_date}; `elo` may
    be None for experience that was declared by a coach rather than fought on
    the platform. Sources already in `to_sport` are skipped — those bouts are
    counted natively.

    Returns discounted wins/losses/draws/bouts, plus `elo_seed`: the rating this
    fighter should start from in `to_sport` instead of a cold `elo_start`, or
    None if nothing transfers.
    """
    wins = losses = draws = 0.0
    elo_seed = None
    for s in sources or []:
        sport = s.get("sport")
        if not sport or sport == to_sport:
            continue
        coef = transfer_coefficient(sport, to_sport) * _transfer_decay(
            s.get("last_bout_date"), as_of
        )
        if coef <= 0:
            continue
        wins   += coef * (s.get("wins")   or 0)
        losses += coef * (s.get("losses") or 0)
        draws  += coef * (s.get("draws")  or 0)
        if s.get("elo") is not None:
            # Take the single most relevant credential rather than an average:
            # experience does not cancel out across disciplines.
            candidate = coef * float(s["elo"])
            elo_seed  = candidate if elo_seed is None else max(elo_seed, candidate)
    return {
        "wins":     wins,
        "losses":   losses,
        "draws":    draws,
        "bouts":    wins + losses + draws,
        "elo_seed": elo_seed,
    }


def _no_credit() -> dict:
    return {"wins": 0.0, "losses": 0.0, "draws": 0.0, "bouts": 0.0, "elo_seed": None}


def experience_mismatch(a_bouts: float, b_bouts: float) -> bool:
    """True when the effective-experience gap is too wide for a competitive fight."""
    low, high = sorted((a_bouts, b_bouts))
    if low < debut_experience_epsilon:
        return high > debut_max_opponent_bouts
    return high > low * experience_ratio_limit + experience_gap_allowance


# ── ELO helpers ────────────────────────────────────────────────────────────

def _season_activity(history: list[dict], before_date: str) -> int:
    """Count fights in the 180 days immediately before before_date."""
    try:
        cutoff = _date.fromisoformat(before_date) - _timedelta(days=180)
        pivot  = _date.fromisoformat(before_date)
    except (ValueError, TypeError):
        return 0
    return sum(
        1 for h in history
        if cutoff <= _date.fromisoformat(h["date"]) < pivot
    )


def _streak_at_date(history: List[dict], before_date: str) -> int:
    past = sorted(
        [h for h in history if h["date"] < before_date],
        key=lambda h: h["date"], reverse=True
    )
    streak = 0
    for h in past:
        if h["result"] == "W":
            streak += 1
        else:
            break
    return streak


def _streak_multiplier(streak: int) -> float:
    if streak < 3:
        return 0.0
    return min(0.4 + (streak - 3) * 0.2, 1.5)


def _total_bouts(fighter: dict) -> int:
    return fighter["wins"] + fighter["losses"] + fighter["draws"]


def _expected(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def _build_context_multiplier(
    result:       str,
    method:       str,
    fighter:      dict,
    fighter_hist: list[dict],
    opponent:     dict,
    opp_hist:     list[dict],
    fight_date:   str,
) -> float:
    is_win  = result.upper() == "W"
    is_loss = result.upper() == "L"

    mult = _method_multiplier(method) if is_win else 1.0

    f_total = _total_bouts(fighter)
    o_total = _total_bouts(opponent)
    f_wins  = fighter["wins"]
    o_wins  = opponent["wins"]

    if is_win:
        f_streak = _streak_at_date(fighter_hist, fight_date)
        mult += _streak_multiplier(f_streak)

    if o_total > 0 and f_total > 0:
        if is_win:
            if o_total > f_total:
                mult += 0.2
            elif o_total < f_total:
                mult -= 0.15
        elif is_loss:
            if o_total < f_total:
                mult -= 0.2

    if is_win:
        opp_streak = _streak_at_date(opp_hist, fight_date)
        if opp_streak >= 3:
            mult += 0.3

    if is_win:
        if o_wins > f_wins:
            mult += 0.25
        elif o_wins < f_wins:
            mult -= 0.1
    elif is_loss:
        if o_wins < f_wins:
            mult -= 0.15

    return max(0.1, mult)


def compute_elo(history: list[dict], all_elos: dict[str, float] | None = None) -> float:
    if all_elos is None:
        all_elos = {}
    rating       = float(elo_start)
    result_score = {"W": 1.0, "D": 0.5, "L": 0.0}
    sorted_hist  = sorted(history, key=lambda h: h["date"])
    for fight in sorted_hist:
        opp_name   = fight["opponent"]
        opp_rating = all_elos.get(opp_name, float(elo_start))
        actual     = result_score.get(fight["result"].upper(), 0.5)
        expected   = _expected(rating, opp_rating)
        multiplier = _method_multiplier(fight["method"]) if actual == 1.0 else 1.0
        change     = elo_k * multiplier * (actual - expected)
        if change < 0:
            change *= loss_dampening
        elif change > 0:
            active = _season_activity(sorted_hist, fight["date"])
            if active >= activity_threshold:
                change *= activity_bonus_mult
            if (opp_rating - rating) >= upset_elo_gap:
                change *= upset_bonus_mult
        change += participation_bonus
        rating  = max(rating + change, elo_min)
        all_elos[opp_name] = max(opp_rating - change, elo_min)
    return round(rating, 2)


def compute_elo_for_pool(
    fighters:  list[dict],
    histories: dict[int, list[dict]],
    seeds:     dict[int, float] | None = None,
) -> dict[int, float]:
    """Rate every fighter in a pool from their fight history.

    `seeds` optionally sets a fighter's starting rating instead of `elo_start`
    — used to carry credit in from another discipline so someone with ten bouts
    elsewhere does not enter as a cold 0. Seeds are always derived from native
    ratings in the source sport, never from another sport's seeded rating, so
    credit cannot chain across three disciplines.
    """
    # Build an ambiguity-safe name→id map: if two fighters share a name,
    # exclude that name from symmetric lookups rather than pick the wrong one.
    _name_counts: dict[str, list[int]] = {}
    for f in fighters:
        _name_counts.setdefault(f["name"], []).append(f["id"])
    name_to_id    = {name: ids[0] for name, ids in _name_counts.items() if len(ids) == 1}
    id_to_fighter = {f["id"]: f for f in fighters}

    all_fights = []
    for f in fighters:
        for fight in histories.get(f["id"], []):
            all_fights.append({**fight, "_fighter_id": f["id"], "_fighter_name": f["name"]})
    all_fights.sort(key=lambda h: h["date"])

    seeds        = seeds or {}
    ratings      = {f["id"]: float(seeds.get(f["id"], elo_start)) for f in fighters}
    result_score = {"W": 1.0, "D": 0.5, "L": 0.0}

    for fight in all_fights:
        fid      = fight["_fighter_id"]
        opp_name = fight["opponent"]
        # Prefer the stored opponent_id (exact), fall back to unambiguous name lookup
        opp_id   = fight.get("opponent_id") or name_to_id.get(opp_name)
        # A stored opponent_id can point outside this pool — nothing stops a
        # fight being logged against a fighter registered in another discipline,
        # and a pool is one discipline. Rate those as an unranked opponent
        # rather than dying on the lookup.
        if opp_id not in ratings:
            opp_id = None
        r_fighter = ratings[fid]
        r_opp     = ratings[opp_id] if opp_id else float(elo_start)

        actual   = result_score.get(fight["result"].upper(), 0.5)
        expected = _expected(r_fighter, r_opp)

        if opp_id:
            multiplier = _build_context_multiplier(
                result=fight["result"],
                method=fight["method"],
                fighter=id_to_fighter[fid],
                fighter_hist=histories.get(fid, []),
                opponent=id_to_fighter[opp_id],
                opp_hist=histories.get(opp_id, []),
                fight_date=fight["date"],
            )
        else:
            multiplier = _method_multiplier(fight["method"]) if actual == 1.0 else 1.0

        change = elo_k * multiplier * (actual - expected)
        if change < 0:
            change *= loss_dampening
        elif change > 0:
            active = _season_activity(histories.get(fid, []), fight["date"])
            if active >= activity_threshold:
                change *= activity_bonus_mult
            if (r_opp - r_fighter) >= upset_elo_gap:
                change *= upset_bonus_mult
        change += participation_bonus
        ratings[fid] = max(ratings[fid] + change, elo_min)
        if opp_id:
            ratings[opp_id] = max(ratings[opp_id] - change, elo_min)

    return {fid: round(r, 2) for fid, r in ratings.items()}


# ── scoring profiles ────────────────────────────────────────────────────────

method_prestige = {
    "ko": 1.5,
    "tko": 0.9,
    "submission": 0.85,
    "decision": 0.5,
    "disqualification": 0.0,
}


def _method_prestige(method: str) -> float:
    return method_prestige.get(method.lower().strip(), 0.5)


def _current_streak(history: list[dict]) -> int:
    streak = 0
    for h in sorted(history, key=lambda h: h["date"], reverse=True):
        if h["result"] == "W":
            streak += 1
        else:
            break
    return streak


def _profile(fighter: dict, history: list[dict], elo: float,
             credit: dict | None = None) -> dict:
    credit = credit or _no_credit()
    native_total = fighter["wins"] + fighter["losses"] + fighter["draws"]
    wins   = fighter["wins"]   + credit["wins"]
    losses = fighter["losses"] + credit["losses"]
    draws  = fighter["draws"]  + credit["draws"]
    total  = wins + losses + draws

    win_fights   = [h for h in history if h["result"] == "W"]
    finish_score = (
        sum(_method_prestige(h["method"]) for h in win_fights) / len(win_fights)
        if win_fights else 0.5
    )
    if win_fights:
        finishes         = sum(1 for h in win_fights if h["method"].lower() not in ("decision", "disqualification"))
        opp_quality_score = finishes / len(win_fights)
    else:
        opp_quality_score = 0.0

    recent = sorted(history, key=lambda h: h["date"], reverse=True)[:5]
    if recent:
        result_value = {"W": 1.0, "D": 0.5, "L": 0.0}
        weights      = [5, 4, 3, 2, 1][:len(recent)]
        weighted_sum = sum(result_value[h["result"]] * w for h, w in zip(recent, weights))
        recent_form  = weighted_sum / sum(weights)
    else:
        recent_form = 0.5

    streak       = _current_streak(history)
    streak_score = min(streak / 6.0, 1.0) if streak >= 3 else 0.0
    form_factor  = (recent_form * 0.6) + (streak_score * 0.4)

    return {
        "total":            total,
        "native_total":     native_total,
        "transferred":      credit["bouts"],
        # No record anywhere means unknown, not a 0% win rate — the old
        # `wins / (total or 1)` made a debutant look identical to an 0-3 fighter.
        "win_rate":         wins / total if total else 0.5,
        "elo":              elo,
        "finish_score":     finish_score,
        "opp_quality_score": opp_quality_score,
        "recent_form":      recent_form,
        "streak":           streak,
        "form_factor":      form_factor,
        "age":              fighter["age"],
        "weight_kg":        fighter["weight_kg"],
    }


def _score_weight(a: dict, b: dict) -> float:
    return max(0.0, 1.0 - abs(a["weight_kg"] - b["weight_kg"]) / 10.0)

def _score_elo(a: dict, b: dict) -> float:
    return max(0.0, 1.0 - abs(a["elo"] - b["elo"]) / 400.0)

def _score_record(a: dict, b: dict) -> float:
    return 1.0 - abs(a["win_rate"] - b["win_rate"])

def _score_form(a: dict, b: dict) -> float:
    return 1.0 - abs(a["form_factor"] - b["form_factor"])

def _score_method(a: dict, b: dict) -> float:
    return 1.0 - abs(a["finish_score"] - b["finish_score"])

def _score_opp_quality(a: dict, b: dict) -> float:
    return 1.0 - abs(a["opp_quality_score"] - b["opp_quality_score"])

def _score_experience(a: dict, b: dict) -> float:
    return max(0.0, 1.0 - abs(a["total"] - b["total"]) / 10.0)

def _score_recent_form(a: dict, b: dict) -> float:
    return 1.0 - abs(a["recent_form"] - b["recent_form"])

def _score_age(a: dict, b: dict) -> float:
    # Date of birth is optional on a profile, so age may be unknown. Score it
    # as neutral rather than raising — this factor carries 3% of the weight and
    # is not worth failing a whole pool over.
    if a["age"] is None or b["age"] is None:
        return 0.5
    return max(0.0, 1.0 - abs(a["age"] - b["age"]) / 10.0)


def match_score(
    fighter:          dict,
    fighter_elo:      float,
    fighter_history:  list[dict],
    opponent:         dict,
    opponent_elo:     float,
    opponent_history: list[dict],
    fighter_credit:   dict | None = None,
    opponent_credit:  dict | None = None,
) -> int:
    a = _profile(fighter,  fighter_history,  fighter_elo,  fighter_credit)
    b = _profile(opponent, opponent_history, opponent_elo, opponent_credit)
    raw = (
        _score_weight(a, b)      * weight_W      +
        _score_elo(a, b)         * elo_w         +
        _score_record(a, b)      * record_w      +
        _score_method(a, b)      * method_W      +
        _score_form(a, b)        * form_w        +
        _score_opp_quality(a, b) * opp_quality_w +
        _score_experience(a, b)  * experience_w  +
        _score_recent_form(a, b) * recent_form_w +
        _score_age(a, b)         * age_w
    )
    return round(raw * 100)


def rank_opponents(
    fighter:            dict,
    fighter_history:    list[dict],
    candidates:         list[dict],
    sport:              str | None = None,
    sources:            dict[int, list[dict]] | None = None,
    include_ineligible: bool = False,
) -> list[dict]:
    """Rank candidate opponents for `fighter`, best match first.

    `sources` maps fighter id → that fighter's record in *other* disciplines
    (see `experience_credit`). When supplied along with `sport`, cross-sport
    experience seeds each fighter's ELO and counts towards their effective
    record, so a boxer with ten bouts does not enter kickboxing looking like a
    debutant.

    Pairings whose experience gap is too wide are dropped rather than merely
    scored down — see `experience_mismatch`. Pass `include_ineligible=True` to
    get them back, flagged and sorted last.
    """
    all_fighters  = [fighter] + [c["fighter"] for c in candidates]
    all_histories = {fighter["id"]: fighter_history}
    for c in candidates:
        all_histories[c["fighter"]["id"]] = c["history"]

    # Fold in whatever each fighter has done in other disciplines.
    credits: dict[int, dict] = {}
    seeds:   dict[int, float] = {}
    if sport and sources:
        for f in all_fighters:
            credit = experience_credit(sources.get(f["id"], []), sport)
            credits[f["id"]] = credit
            if credit["elo_seed"] is not None:
                seeds[f["id"]] = credit["elo_seed"]

    elo_ratings = compute_elo_for_pool(all_fighters, all_histories, seeds)
    fighter_elo = elo_ratings[fighter["id"]]

    fighter_credit = credits.get(fighter["id"]) or _no_credit()
    fighter_bouts  = _total_bouts(fighter) + fighter_credit["bouts"]

    results = []
    for c in candidates:
        opp        = c["fighter"]
        opp_elo    = elo_ratings[opp["id"]]
        opp_credit = credits.get(opp["id"]) or _no_credit()
        opp_bouts  = _total_bouts(opp) + opp_credit["bouts"]

        # Divisions are single-sex. Unlike an experience gap — which a
        # promoter may reasonably choose to look at and override — a mixed
        # pairing is dropped outright and is never returned, not even under
        # include_ineligible. Offering one at all would be the bug.
        #
        # Both sides must be known for this to bite: a fighter with no gender
        # recorded is missing data, not a mismatch, and excluding them would
        # silently empty the matchmaker for every profile created before the
        # field existed.
        if fighter.get("gender") and opp.get("gender")                 and fighter["gender"] != opp["gender"]:
            continue

        eligible = not experience_mismatch(fighter_bouts, opp_bouts)
        if not eligible and not include_ineligible:
            continue

        score = match_score(
            fighter, fighter_elo, fighter_history,
            opp,     opp_elo,     c["history"],
            fighter_credit, opp_credit,
        )
        row = {
            **opp,
            "elo":               opp_elo,
            "elo_band":          elo_band(opp_elo),
            "match_score":       score,
            "weight_diff":       round(abs(fighter["weight_kg"] - opp["weight_kg"]), 1),
            "effective_bouts":   round(opp_bouts, 1),
            "transferred_bouts": round(opp_credit["bouts"], 1),
        }
        if include_ineligible:
            row["eligible"] = eligible
            if not eligible:
                row["ineligible_reason"] = "experience_mismatch"
        results.append(row)

    results.sort(key=lambda x: (x.get("eligible", True), x["match_score"]), reverse=True)
    return results
