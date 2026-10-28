"""What does the screen select for?  Runs the minimal-pair screen over a range of seeds
and reports pass rates under several nuisance-screen settings, how often each printed
characteristic fails, and how the screened packets' observed effects compare with the
planted ones.

  python tools/screen_stats.py --start 50000 --n 2000 [--no-smoking-gun] [--delta 0.4 --tau 0.25]
"""
import argparse
import collections
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synthlit.generate import (VARIANTS, DELTA_DEFAULT, TAU_DEFAULT, simulate, oracle,  # noqa: E402
                               passes_screen, passes_structure, nuisance_tests, nuisance_family, nuisance_ok)

# (label, families, alpha)
CONFIGS = [
    ("marginal p>=.10", ("marginal",), 0.10),
    ("marginal+adjusted p>=.10", ("marginal", "adjusted"), 0.10),
    ("marginal+adjusted p>=.05", ("marginal", "adjusted"), 0.05),
    ("all families p>=.05", ("marginal", "adjusted", "within"), 0.05),
    ("all families p>=.10", ("marginal", "adjusted", "within"), 0.10),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=50000)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--no-smoking-gun", action="store_true")
    ap.add_argument("--delta", type=float, default=DELTA_DEFAULT)
    ap.add_argument("--tau", type=float, default=TAU_DEFAULT)
    a = ap.parse_args()
    passed = collections.Counter()
    fails = collections.Counter()   # (variant, characteristic, family) -> structure-passing pairs failing it at .10
    stats = collections.defaultdict(list)
    for seed in range(a.start, a.start + a.n):
        runs = {}
        for vn in VARIANTS:
            st = simulate(vn, seed, smoking_gun=not a.no_smoking_gun, delta=a.delta, tau=a.tau)
            runs[vn] = (st, oracle(st, nuisance=False))
        groups = ["all"]
        if all(passes_screen(vn, st, orc, "v03") for vn, (st, orc) in runs.items()):
            passed["v0.3 screen"] += 1; groups.append("v0.3 screen")
        if all(passes_structure(vn, st, orc) for vn, (st, orc) in runs.items()):
            passed["structure"] += 1
            for vn, (st, orc) in runs.items():
                orc["nuisance"] = nuisance_tests(st)
                failing = {(name.split(":")[0], nuisance_family(name)) for name, p in orc["nuisance"].items()
                           if p is not None and p < 0.10}
                for ch, fam in failing:
                    fails[(vn, ch, fam)] += 1
            for label, fams, alpha in CONFIGS:
                if all(nuisance_ok(orc["nuisance"], fams, alpha) for _, orc in runs.values()):
                    passed[label] += 1; groups.append(label)
        for vn, (st, orc) in runs.items():
            lv = orc["categorical"]["contrast_type"]["levels"]
            for g in groups:
                stats[(g, vn, "vs_neutral")].append(lv["vs_neutral"]["estimate"])
                stats[(g, vn, "vs_low_level")].append(lv["vs_low_level"]["estimate"])
                stats[(g, vn, "within_I2")].append(orc["dispersion_within_contrast"]["I2"])
    n = a.n; ns = passed["structure"]
    print(f"seeds {a.start}..{a.start + n - 1}, clue {'absent' if a.no_smoking_gun else 'present'}, delta {a.delta}, tau {a.tau}")
    print(f"\nPairs passing (of {n}):")
    for label in ["structure", "v0.3 screen"] + [c[0] for c in CONFIGS]:
        print(f"  {label:28s} {passed[label]:5d}  ({passed[label] / n:.2%})")
    if ns:
        print(f"\nAmong {ns} pairs passing the structural screen: % of packets where a characteristic fails at p < .10, by test family")
        chars = sorted({(vn, ch) for vn, ch, _ in fails})
        print(f"  {'variant':18s} {'characteristic':17s} marginal adjusted within")
        for vn, ch in chars:
            print(f"  {vn:18s} {ch:17s} " + " ".join(f"{fails[(vn, ch, f)] / ns:7.0%} " for f in ("marginal", "adjusted", "within")))
    planted = {"baseline_artifact": {"vs_neutral": -a.delta, "vs_low_level": 0.0},
               "true_blunting": {"vs_neutral": -a.delta, "vs_low_level": -a.delta}}
    print("\nMedian observed estimate [planted] and within-contrast I^2, by screen passed:")
    for vn in VARIANTS:
        for q in ["vs_neutral", "vs_low_level", "within_I2"]:
            tag = f"[{planted[vn][q]:+.2f}]" if q in planted[vn] else ""
            row = [f"{g}: {np.median(stats[(g, vn, q)]):+.3f}" for g in ["all", "v0.3 screen"] + [c[0] for c in CONFIGS]
                   if len(stats[(g, vn, q)]) >= 5]
            print(f"  {vn:18s} {q:13s}{tag:8s} " + " | ".join(row))


if __name__ == "__main__":
    main()
