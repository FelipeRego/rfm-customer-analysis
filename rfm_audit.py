"""Audit the segmentation: does it do what the documentation says it does?

Two passes, and they answer different questions.

PASS 1 — Reachability (pure Python, no API, no cost).
    `segment()` in rfm_analysis.py is an ordered if-chain, but README.md documents
    it as a flat table of criteria. Those are not the same thing: an earlier rule
    shadows a later one whose conditions also match. This pass lifts the real
    function out of the source with `ast`, runs all 25 R×F combinations through it,
    and reports which documented segments can never actually be assigned, and where
    the documented criteria disagree with the code.

    This is the pass that finds bugs. It needs no model, and it is the one to fix
    against — do not paper over a rule-ordering defect with a probability.

PASS 2 — Semantic cross-check (Jev).
    Reachability proves the chain is self-consistent; it cannot tell you whether
    "Need Attention" is a sensible name for the customers landing in it. This pass
    describes each customer's behaviour in plain words, hands Jev all the segment
    descriptions, and asks which one fits best. Disagreements with the code's own
    assignment are flagged for a human — as a standing guard against a future
    reorder quietly changing what a label means.

    python rfm_audit.py                # both passes
    python rfm_audit.py --rules-only   # pass 1 only, no API needed
    python rfm_audit.py --sample 25    # limit pass 2 to 25 customers
"""

import ast
import csv
import sys

from typesafe_sdk import Choice, Noul

import jev

# ── CONFIG ────────────────────────────────────────────────────────────────────
SOURCE_FILE   = 'rfm_analysis.py'
ANALYSIS_FILE = 'rfm_analysis.csv'

RULES_ONLY = '--rules-only' in sys.argv
SAMPLE     = int(sys.argv[sys.argv.index('--sample') + 1]) if '--sample' in sys.argv else None

# The result grid exactly as README.md publishes it, transcribed by hand from the
# docs rather than generated from the code — the whole point is to compare the two.
#
# The grid, not the rule list, is the specification. The rules overlap, so a single
# rule cannot be checked in isolation; the grid states unambiguously what every
# (r, f) pair resolves to. Reorder the chain in rfm_analysis.py and this diff fails.
DOCUMENTED_GRID = {
    5: {1: 'New Customer', 2: 'Potential Loyalist', 3: 'Loyal', 4: 'Champions',       5: 'Champions'},
    4: {1: 'New Customer', 2: 'Potential Loyalist', 3: 'Loyal', 4: 'Champions',       5: 'Champions'},
    3: {1: 'Promising',    2: 'Need Attention',     3: 'Loyal', 4: 'Loyal',           5: 'Loyal'},
    2: {1: 'Hibernating',  2: 'About to Sleep',     3: 'At Risk', 4: 'At Risk',       5: 'At Risk'},
    1: {1: 'Lost',         2: 'Lost',               3: 'At Risk', 4: "Can't Lose Them", 5: "Can't Lose Them"},
}

# Plain-English meaning of each segment, for the semantic pass.
DESCRIPTIONS = {
    'Champions':          "Buys often and bought very recently. Among the best customers we have.",
    'Loyal':              "Buys consistently and regularly, and is still active.",
    'Potential Loyalist': "Bought recently and has started to repeat, but the habit isn't established.",
    'Promising':          "Bought recently, but only once or twice. Too early to tell.",
    'New Customer':       "Bought for the first time very recently.",
    'Need Attention':     "Was a moderate, regular buyer and is now drifting. Middling on every measure.",
    'About to Sleep':     "Bought a little, a while ago. Engagement is fading.",
    'Hibernating':        "Bought once or twice, a long time ago. Dormant but not necessarily gone.",
    'At Risk':            "Used to buy often, and has now gone quiet. A valuable habit is breaking.",
    "Can't Lose Them":    "Was one of our most frequent buyers and has gone silent. The biggest loss if unrecovered.",
    'Lost':               "Bought rarely, a long time ago, and shows no sign of returning.",
}


# ── PASS 1 — REACHABILITY ─────────────────────────────────────────────────────
def load_segment_fn(path):
    """Lift the real `segment()` out of rfm_analysis.py without running the script."""
    tree = ast.parse(open(path).read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'segment':
            ns = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), ns)
            return ns['segment']
    raise SystemExit(f"No segment() found in {path}")


def reachability(segment_fn):
    grid      = {(r, f): segment_fn(r, f) for r in range(1, 6) for f in range(1, 6)}
    reachable = set(grid.values())
    documented = {s for row in DOCUMENTED_GRID.values() for s in row.values()}

    print("=== Pass 1 — Code vs. documentation (deterministic, no API) ===\n")
    print("  Segment assigned for each R (rows) × F (cols) combination:\n")
    print("        " + "".join(f"F={f:<19}" for f in range(1, 6)))
    for r in range(5, 0, -1):
        print(f"  R={r}  " + "".join(f"{grid[(r, f)]:<21}" for f in range(1, 6)))

    # 1. Does the code produce what README.md publishes?
    diffs = [(r, f, grid[(r, f)], DOCUMENTED_GRID[r][f])
             for r in range(1, 6) for f in range(1, 6)
             if grid[(r, f)] != DOCUMENTED_GRID[r][f]]

    if diffs:
        print(f"\n  !! GRID MISMATCH — {len(diffs)} of 25 cells differ from README.md:")
        for r, f, actual, doc in diffs:
            print(f"       R={r} F={f}: code assigns {actual!r}, README documents {doc!r}")
        print("\n     Either the chain in rfm_analysis.py was reordered, or the README")
        print("     grid is stale. One of the two is wrong and both cannot be trusted.")
    else:
        print(f"\n  Grid matches README.md on all 25 combinations.")

    # 2. Can every documented segment actually be assigned?
    orphans = sorted(documented - reachable)
    if orphans:
        print(f"\n  !! UNREACHABLE — documented but never assigned: {', '.join(orphans)}")
    else:
        print(f"  All {len(reachable)} documented segments are reachable.")

    # 3. Does the out-of-range guard actually fire?
    #    (0, 3) is the probe that matters: it satisfies `r <= 2 and f >= 3`, so without
    #    an explicit range check it comes back as a confident 'At Risk'.
    bad = []
    for r, f in [(0, 3), (0, 0), (6, 6), (3, 9), (-1, 2)]:
        try:
            label = segment_fn(r, f)
            bad.append(f'({r}, {f}) -> {label!r}')
        except (ValueError, AssertionError):
            pass
    if bad:
        print(f"\n  !! No range guard — out-of-range scores return a label instead of raising:")
        for b in bad:
            print(f"       {b}")
    else:
        print("  Out-of-range scores raise rather than being silently mislabelled.")

    if not diffs and not orphans:
        print("\n  Clean: code and documentation agree.")
    return grid


# ── PASS 2 — SEMANTIC CROSS-CHECK ─────────────────────────────────────────────
def describe(c):
    """Put a customer's behaviour in words. Jev judges meaning; code owns the numbers."""
    rec, freq, spend = int(c['recency']), int(c['frequency']), float(c['monetaryValue'])
    when = ("within the last month" if rec <= 30 else
            "one to three months ago" if rec <= 90 else
            "three to six months ago" if rec <= 180 else "more than six months ago")
    how  = ("just once" if freq == 1 else
            "a couple of times" if freq <= 2 else
            "several times" if freq <= 4 else "many times")
    return (f"This customer has bought {how} from us in total, spending ${spend:,.0f} "
            f"altogether. Their most recent purchase was {when} ({rec} days ago).")


def semantic_pass(customers, grid):
    qs = {
        'best_fit': Choice(
            instructions=(
                "`customer` describes one customer's buying behaviour. Which of these "
                "descriptions of customer types fits them best?"
            ),
            criteria=dict(DESCRIPTIONS),
        ),
        'assigned_fits': Noul(
            instructions=(
                "`customer` describes one customer's buying behaviour, and `assigned_label` "
                "is the description our system has already filed them under. Is that a fair "
                "description of this customer?"
            ),
        ),
    }

    print("\n\n=== Pass 2 — Semantic cross-check (Jev) ===\n")
    rows = customers[:SAMPLE] if SAMPLE else customers
    print(f"  Checking {len(rows)} customers...\n")

    disagreements = []
    for c in rows:
        assigned = c['segment']
        answers  = jev.ask({
            'customer':        describe(c),
            'assigned_label':  DESCRIPTIONS.get(assigned, assigned),
        }, qs)

        best = answers['best_fit']
        fits = answers['assigned_fits']['noul']
        if best['choice'] != assigned or fits < 0.5:
            disagreements.append({
                'customerid': c['customerid'],
                'assigned':   assigned,
                'best_fit':   best['choice'],
                'confidence': best['confidence'],
                'fits':       fits,
            })

    if not disagreements:
        print("  No disagreements. Every assignment reads as fair.")
        return

    print(f"  {len(disagreements)} of {len(rows)} assignments Jev reads differently:\n")
    print(f"  {'customer':<11} {'code assigned':<20} {'Jev would say':<20} {'conf':>5} {'fits':>6}")
    for d in sorted(disagreements, key=lambda d: d['fits'])[:20]:
        print(f"  {d['customerid']:<11} {d['assigned']:<20} {d['best_fit']:<20} "
              f"{d['confidence']:>5.2f} {d['fits']:>6.2f}")
    if len(disagreements) > 20:
        print(f"  ... and {len(disagreements) - 20} more")

    pairs = {}
    for d in disagreements:
        pairs[(d['assigned'], d['best_fit'])] = pairs.get((d['assigned'], d['best_fit']), 0) + 1
    print(f"\n  Most common disagreements:")
    for (a, b), n in sorted(pairs.items(), key=lambda x: -x[1])[:5]:
        print(f"    {n:>3}x  code: {a:<20} → Jev: {b}")
    print("\n  These are review candidates, not defects. A disagreement means the label and")
    print("  the behaviour read differently to a fresh eye — worth checking the rule order.")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    jev.banner()
    grid = reachability(load_segment_fn(SOURCE_FILE))

    if not RULES_ONLY:
        with open(ANALYSIS_FILE) as f:
            customers = list(csv.DictReader(f))
        semantic_pass(customers, grid)
