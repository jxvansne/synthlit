"""What does the v0.5 screen select for, at a given literature size?

For each seed it simulates one literature and records whether the target passes the
structural screen and the clue check, whether it is clean or has a usable distractor, and
whether a control trade exists. It reports pass rates, and the observed effects in passing
literatures against the planted ones (the inflation the screen causes).

  python tools/screen_stats.py --k 20 --start 50000 --n 2000
"""
import argparse
import collections
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synthlit.generate import (DELTA_DEFAULT, TAU_DEFAULT, simulate, oracle, target_structure_ok,  # noqa: E402
                               clue_ok, nuisance_tests, classify_nuisance, make_control)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--start", type=int, default=50000)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--delta", type=float, default=DELTA_DEFAULT)
    ap.add_argument("--tau", type=float, default=TAU_DEFAULT)
    a = ap.parse_args()
    count = collections.Counter()
    est = collections.defaultdict(list)
    for seed in range(a.start, a.start + a.n):
        lit = simulate(seed, a.k, a.delta, a.tau)
        orc = oracle(lit, "target", nuisance=False)
        lv = orc["categorical"]["contrast_type"]["levels"]
        groups = ["all seeds"]
        if target_structure_ok(orc):
            count["structure"] += 1
            groups.append("structure")
            if clue_ok(lit):
                count["structure+clue"] += 1
                cond, distractors = classify_nuisance(lit, nuisance_tests(lit, "target"))
                if cond:
                    lit.condition, lit.distractors = cond, distractors
                    count[cond] += 1
                    if make_control(lit, max_tries=1000):
                        count[f"{cond}, control found"] += 1
                        groups.append(f"{cond} set")
                        corc = oracle(lit, "control", nuisance=False)["categorical"]["contrast_type"]["levels"]
                        est[(f"{cond} set", "control NEG-NEU")].append(corc["neg_minus_neu"]["estimate"])
                        est[(f"{cond} set", "control NEG-only")].append(corc["neg_only"]["estimate"])
        for g in groups:
            est[(g, "target NEG-NEU")].append(lv["neg_minus_neu"]["estimate"])
            est[(g, "target NEG-only")].append(lv["neg_only"]["estimate"])
            est[(g, "within-contrast I2")].append(orc["dispersion_within_contrast"]["I2"])
    n = a.n
    print(f"k = {a.k}, delta = {a.delta}, tau = {a.tau}, seeds {a.start}..{a.start + n - 1}")
    for c in ["structure", "structure+clue", "clean", "clean, control found", "distractor", "distractor, control found"]:
        print(f"  {c:28s} {count[c]:5d}  ({count[c] / n:6.2%} of seeds)")
    print("  median estimates (planted: target NEG-NEU -%.2f, target NEG-only 0, control both about -%.2f):" % (a.delta, a.delta / 2))
    for q in ["target NEG-NEU", "target NEG-only", "control NEG-NEU", "control NEG-only", "within-contrast I2"]:
        cells = [f"{g}: {np.median(est[(g, q)]):+.3f}" for g in ["all seeds", "structure", "clean set", "distractor set"]
                 if len(est[(g, q)]) >= 3]
        print(f"    {q:20s} " + " | ".join(cells))


if __name__ == "__main__":
    main()
