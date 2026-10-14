"""Read back what the matchmaker did with the multi-division fixture.

Seeding the data only sets the question. This prints the answer: for every
fighter whose experience lives in another discipline, what credit they were
given, where it came from, what rating they entered on, who they were offered,
and who was filtered out before scoring.

It computes nothing of its own beyond arithmetic already inside the matchmaker
— every number here comes from `FighterService` and `matchmaker`, so the report
cannot agree with the algorithm while the app disagrees with it.
"""

from ..models.fighter import Fighter
from .fighter_service import FighterService
from .matchmaker import (
    _transfer_decay, elo_band, experience_credit, experience_mismatch,
    transfer_coefficient, debut_max_opponent_bouts,
    experience_gap_allowance, experience_ratio_limit,
)
from .multidivision_seed import NOTE

RULE = "─" * 78


def _fixture(sport: str = None):
    """Fixture fighters (recognised by the NOTE prefix on their description)."""
    q = Fighter.query.filter(Fighter.description.like(f"{NOTE}%"))
    if sport:
        q = q.filter(Fighter.sport == sport)
    return q.order_by(Fighter.name).all()


def _find(name: str, sport: str):
    """One fixture fighter by name, or None."""
    return next((f for f in _fixture(sport) if f.name == name), None)


def _bouts(f: Fighter) -> int:
    """Native bouts on the fighter's record."""
    r = f.record
    return (r.wins + r.losses + r.draws) if r else 0


def _record_str(f: Fighter) -> str:
    """Record as "W-L-D"."""
    r = f.record
    return f"{r.wins}-{r.losses}-{r.draws}" if r else "0-0-0"


# ── section 1: where each crossover's credit comes from ────────────────────

def transfer_register(sport: str, out) -> None:
    """Section 1: for each crossover in `sport`, list where its credit came from."""
    svc     = FighterService(sport)
    pool    = _fixture(sport)
    ids     = [f.id for f in pool]
    sources = svc.experience_sources(ids)
    elos    = svc.elo_pool()

    out(f"\n{RULE}\nTRANSFER REGISTER — {sport}\n{RULE}")
    out("Fighters carrying experience in from another discipline. `eff` is the")
    out("effective bout count matchmaking uses; native bouts count 1.0 each.\n")

    any_found = False
    for f in pool:
        src = [s for s in sources.get(f.id, []) if s["sport"] != sport]
        if not src:
            continue
        any_found = True
        credit = experience_credit(src, sport)
        native = _bouts(f)
        elo    = elos.get(f.id, 0.0)

        out(f"  {f.name} ({f.gender}, {f.weight:g} kg) — native {_record_str(f)}")
        for s in src:
            coef  = transfer_coefficient(s["sport"], sport)
            decay = _transfer_decay(s.get("last_bout_date"))
            n     = (s["wins"] or 0) + (s["losses"] or 0) + (s["draws"] or 0)
            origin = "declared" if s.get("declared") else "linked profile"
            out(f"      from {s['sport']:<11} {s['wins']}-{s['losses']}-{s['draws']}"
                f"  ({n} bouts, {origin}, last {s.get('last_bout_date') or 'unknown'})")
            out(f"        transfer {coef:.2f} × decay {decay:.3f} = {coef * decay:.3f}"
                f"  →  {n * coef * decay:5.2f} bouts")
            if s.get("elo") is not None:
                out(f"        rating there {s['elo']:.1f} → seed candidate "
                    f"{coef * decay * float(s['elo']):.1f}")
            else:
                out("        no rating transfers — declared, never fought here")

        seed = credit["elo_seed"]
        out(f"      credit: {credit['wins']:.2f}-{credit['losses']:.2f}-"
            f"{credit['draws']:.2f}  ({credit['bouts']:.2f} bouts)")
        out(f"      eff bouts {native + credit['bouts']:.2f}"
            f"   seed {('none (cold 0)' if seed is None else f'{seed:.1f}')}"
            f"   rating {elo:.1f} ({elo_band(elo)})\n")

    if not any_found:
        out("  (nobody in this division has experience elsewhere)\n")


# ── section 2: the matched pairs ──────────────────────────────────────────

def _eff(sport: str, name: str) -> tuple:
    """(native bouts, transferred bouts, effective bouts, elo) for one profile."""
    svc = FighterService(sport)
    f   = _find(name, sport)
    if not f:
        return (0, 0.0, 0.0, 0.0)
    src    = svc.experience_sources([f.id]).get(f.id, [])
    credit = experience_credit(src, sport)
    elo    = svc.elo_pool().get(f.id, 0.0)
    return (_bouts(f), credit["bouts"], _bouts(f) + credit["bouts"], elo)


def paired_comparisons(out) -> None:
    """Section 2: compare each A/B pair from the fixture side by side."""
    out(f"\n{RULE}\nPAIRED COMPARISONS — one variable changed at a time\n{RULE}")

    # ── direction of travel ───────────────────────────────────────────────
    vane_kb = _eff("kickboxing", "Marcus Vane")
    ruiz_bx = _eff("boxing", "Declan Ruiz")
    vane_bx = _eff("boxing", "Marcus Vane")
    ruiz_kb = _eff("kickboxing", "Declan Ruiz")

    out("\n1. SAME RECORD, OPPOSITE DIRECTIONS")
    out("   Vane is 18-2 in boxing and debuting in kickboxing; Ruiz is 18-2 in")
    out("   kickboxing and debuting in boxing. The transfer matrix is asymmetric")
    out("   on purpose — a boxer's hands carry further into kickboxing than a")
    out("   kickboxer's carry into pure boxing.")
    out(f"   boxing→kickboxing  coef {transfer_coefficient('boxing', 'kickboxing'):.2f}"
        f"   Vane enters kickboxing on {vane_kb[2]:.2f} eff bouts"
        f" (rating {vane_kb[3]:.1f}, from {vane_bx[0]} native boxing bouts)")
    out(f"   kickboxing→boxing  coef {transfer_coefficient('kickboxing', 'boxing'):.2f}"
        f"   Ruiz enters boxing on {ruiz_bx[2]:.2f} eff bouts"
        f" (rating {ruiz_bx[3]:.1f}, from {ruiz_kb[0]} native kickboxing bouts)")
    gap = vane_kb[2] - ruiz_bx[2]
    out(f"   → the same career is worth {gap:+.2f} more bouts going one way"
        f" than the other")

    # ── decay ─────────────────────────────────────────────────────────────
    pros_kb = _eff("kickboxing", "Alan Prosser")
    berr_kb = _eff("kickboxing", "Kyle Berrow")
    pros_bx = _eff("boxing", "Alan Prosser")
    berr_bx = _eff("boxing", "Kyle Berrow")

    out("\n2. SAME RECORD, DIFFERENT DECADE")
    out("   Prosser and Berrow are both 20-5 boxers debuting in kickboxing.")
    out("   Prosser last fought eight years ago; Berrow fought this year.")
    out(f"   Prosser  boxing {pros_bx[0]} bouts  →  {pros_kb[2]:.2f} eff in kickboxing"
        f"  (rating {pros_kb[3]:.1f}, {elo_band(pros_kb[3])})")
    out(f"   Berrow   boxing {berr_bx[0]} bouts  →  {berr_kb[2]:.2f} eff in kickboxing"
        f"  (rating {berr_kb[3]:.1f}, {elo_band(berr_kb[3])})")
    out(f"   → decay costs the identical record {berr_kb[2] - pros_kb[2]:.2f} bouts,")
    out("     floored so it never reaches zero: having been in there still counts")

    # ── two credentials at once ───────────────────────────────────────────
    svc  = FighterService("kickboxing")
    femi = _find("Femi Adeyemi", "kickboxing")
    out("\n3. TWO CREDENTIALS AT ONCE")
    out("   Adeyemi holds an mma profile and a boxing profile, and is debuting")
    out("   in kickboxing. Bouts add; the rating seed does not.")
    if femi:
        src    = svc.experience_sources([femi.id]).get(femi.id, [])
        credit = experience_credit(src, "kickboxing")
        candidates = []
        for s in src:
            coef  = transfer_coefficient(s["sport"], "kickboxing")
            decay = _transfer_decay(s.get("last_bout_date"))
            n     = (s["wins"] or 0) + (s["losses"] or 0) + (s["draws"] or 0)
            out(f"   {s['sport']:<11} {n:2d} bouts × {coef * decay:.3f} = "
                f"{n * coef * decay:5.2f} bouts", )
            if s.get("elo") is not None:
                c = coef * decay * float(s["elo"])
                candidates.append((s["sport"], c))
                out(f"                rating {s['elo']:7.1f} × {coef * decay:.3f}"
                    f" = seed candidate {c:.1f}")
        out(f"   bouts total {credit['bouts']:.2f} — summed across both")
        if candidates:
            best = max(candidates, key=lambda c: c[1])
            out(f"   seed  {credit['elo_seed']:.1f} — the single best credential"
                f" ({best[0]}), not the sum ({sum(c for _, c in candidates):.1f})"
                f" and not the mean ({sum(c for _, c in candidates) / len(candidates):.1f})")
        out("   the source ratings are unseeded ratings in their own division, so")
        out("   credit cannot chain mma → boxing → kickboxing and compound")

    # ── declared vs linked ────────────────────────────────────────────────
    hlavac = _eff("kickboxing", "Tomas Hlavac")
    pike   = _eff("kickboxing", "Owen Pike")
    out("\n4. DECLARED EXPERIENCE — BOUTS WITHOUT A RATING")
    out("   Neither has a linked profile; a coach declared their record. Both")
    out("   get experience credit, neither gets a rating seed.")
    out(f"   Hlavac  muaythai 14-3 × {transfer_coefficient('muaythai', 'kickboxing'):.2f}"
        f"  →  {hlavac[2]:.2f} eff bouts, rating {hlavac[3]:.1f}")
    out(f"   Pike    mma      10-2 × {transfer_coefficient('mma', 'kickboxing'):.2f}"
        f"  →  {pike[2]:.2f} eff bouts, rating {pike[3]:.1f}")
    out("   → both enter on a cold rating but a real bout count, so the")
    out("     experience filter protects them while ELO still treats them as new")


# ── section 3: what the matchmaker actually offers ────────────────────────

def match_list(sport: str, name: str, out, limit: int = 6) -> None:
    """Print the top `limit` opponents offered to one fighter, plus who was filtered."""
    svc = FighterService(sport)
    f   = _find(name, sport)
    if not f:
        out(f"  {name} not found in {sport}")
        return

    src     = svc.experience_sources([f.id]).get(f.id, [])
    credit  = experience_credit(src, sport)
    eff     = _bouts(f) + credit["bouts"]
    elo     = svc.elo_pool().get(f.id, 0.0)

    rows = svc.get_matches(f.id, include_ineligible=True)
    ok   = [r for r in rows if r.get("eligible", True)]
    bad  = [r for r in rows if not r.get("eligible", True)]

    out(f"\n  {name} — {sport}, {f.gender}, {f.weight:g} kg, "
        f"native {_record_str(f)}, eff {eff:.2f} bouts, "
        f"rating {elo:.1f} ({elo_band(elo)})")
    out(f"    {'opponent':<18}{'score':>6}{'rating':>9}{'band':>11}"
        f"{'eff':>7}{'xfer':>7}{'Δkg':>7}")
    for r in ok[:limit]:
        out(f"    {r['name']:<18}{r['match_score']:>6}{r['elo']:>9.1f}"
            f"{r['elo_band']:>11}{r['effective_bouts']:>7.1f}"
            f"{r['transferred_bouts']:>7.1f}{r['weight_diff']:>7.1f}")
    if len(ok) > limit:
        out(f"    … {len(ok) - limit} more eligible")
    if not ok:
        out("    (no eligible opponents)")

    if bad:
        out(f"    filtered out ({len(bad)}): " +
            ", ".join(f"{r['name']} [{r['effective_bouts']:.1f}]" for r in bad[:8]) +
            (" …" if len(bad) > 8 else ""))

    # Whoever is missing from both lists was dropped before scoring — the only
    # thing that does that is the single-sex division rule.
    shown  = {r["id"] for r in rows}
    hidden = [c for c in _fixture(sport) if c.id != f.id and c.id not in shown]
    if hidden:
        out(f"    never offered ({len(hidden)}, different division): " +
            ", ".join(f"{c.name} ({c.gender})" for c in hidden[:6]) +
            (" …" if len(hidden) > 6 else ""))


def match_lists(out) -> None:
    """Section 3: match lists for the crossovers, the controls and the women."""
    out(f"\n{RULE}\nWHAT THE MATCHMAKER OFFERS\n{RULE}")
    out("`eff` and `xfer` are the opponent's effective and transferred bouts.")
    out("Filtered-out rows failed the experience gap; never-offered rows are a")
    out("different sex and are dropped before scoring, not ranked last.")

    out("\n── the crossovers ──")
    for name in ("Marcus Vane", "Alan Prosser", "Kyle Berrow",
                 "Femi Adeyemi", "Tomas Hlavac", "Owen Pike"):
        match_list("kickboxing", name, out)
    match_list("boxing", "Declan Ruiz", out)

    out("\n── controls: natives at the same experience level ──")
    match_list("kickboxing", "Petr Novak", out)
    match_list("kickboxing", "Sam Oakley", out)

    out("\n── the female division ──")
    match_list("kickboxing", "Rhiannon Pace", out)


# ── section 4: the filters, stated as rules and then tested ───────────────

def filter_checks(out) -> None:
    """Section 4: state the experience-gap rules, then test them."""
    out(f"\n{RULE}\nFILTER BEHAVIOUR\n{RULE}")
    out(f"  A true debutant may face at most {debut_max_opponent_bouts} effective bouts.")
    out(f"  Otherwise the cap is {experience_ratio_limit} × your bouts"
        f" + {experience_gap_allowance}.\n")

    subjects = [
        ("kickboxing", "Sam Oakley",    "true debutant"),
        ("kickboxing", "Marcus Vane",   "debutant on paper, 20-bout boxer"),
        ("kickboxing", "Alan Prosser",  "debutant on paper, decayed credit"),
        ("kickboxing", "Tomas Hlavac",  "debutant on paper, declared muaythai"),
        ("boxing",     "Declan Ruiz",   "debutant on paper, 20-bout kickboxer"),
        ("boxing",     "Nathan Cole",   "true debutant"),
    ]
    for sport, name, label in subjects:
        native, xfer, eff, _ = _eff(sport, name)
        verdict = ("treated as a debutant"
                   if eff < 0.5 else f"treated as a {eff:.1f}-bout fighter")
        out(f"  {name:<16} {sport:<11} native {native:>2}  xfer {xfer:>5.2f}"
            f"  eff {eff:>5.2f}  → {verdict}  ({label})")

    out("\n  Pairings the experience filter refuses:")
    pairs = [
        ("kickboxing", "Sam Oakley",   "Marcus Vane"),
        ("kickboxing", "Sam Oakley",   "Ivan Dobrev"),
        ("kickboxing", "Marcus Vane",  "Petr Novak"),
        ("kickboxing", "Alan Prosser", "Callum Reid"),
        ("kickboxing", "Alan Prosser", "Dwayne Ellis"),
        ("boxing",     "Nathan Cole",  "Declan Ruiz"),
    ]
    for sport, a_name, b_name in pairs:
        a = _eff(sport, a_name)
        b = _eff(sport, b_name)
        bad = experience_mismatch(a[2], b[2])
        out(f"    {a_name} ({a[2]:5.2f}) vs {b_name} ({b[2]:5.2f})  →  "
            f"{'REFUSED' if bad else 'allowed'}")

    out("\n  The single-sex rule, which is a drop and not a penalty:")
    svc  = FighterService("kickboxing")
    pace = _find("Rhiannon Pace", "kickboxing")
    if pace:
        rows  = svc.get_matches(pace.id, include_ineligible=True)
        names = {r["name"] for r in rows}
        males = [f.name for f in _fixture("kickboxing") if f.gender == "male"]
        leaked = sorted(names & set(males))
        out(f"    Pace is offered {len(rows)} opponents, "
            f"{len([r for r in rows if r.get('eligible', True)])} of them eligible")
        out(f"    male profiles appearing anywhere in her list: "
            f"{leaked if leaked else 'none'}")
        out("    (include_ineligible=True returns experience mismatches but still")
        out("     never returns a mixed pairing — that one is dropped outright)")


# ── entry point ───────────────────────────────────────────────────────────

def report(out=print) -> None:
    """Print the full report through `out` (one call per line)."""
    if not _fixture():
        out("No multi-division fixture in the database. "
            "Run: flask --app wsgi seed-multidivision")
        return

    out(f"{RULE}\nMULTI-DIVISION MATCHMAKING REPORT\n{RULE}")
    counts = {}
    for f in _fixture():
        counts[f.sport] = counts.get(f.sport, 0) + 1
    out("Fixture: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    out("Almost every fighter is 70.0 kg and 24–29, so weight and age sit near")
    out("1.0 for every pairing and the cross-division factors are what move the")
    out("score. Weight twins at 62 and 78 kg are there as the exception.")

    for sport in ("kickboxing", "boxing"):
        transfer_register(sport, out)
    paired_comparisons(out)
    match_lists(out)
    filter_checks(out)
    out(f"\n{RULE}\n")
