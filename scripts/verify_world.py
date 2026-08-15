"""Sanity checks for world.py — run after ANY edit to the world.

Asserts the adversarial shape the whole lab stands on:
  1. every party has at least one perfect (1.0) answer,
  2. the top-rated restaurant FAILS the signature party p3,
  3. an optimizer pointed at rating_score would always pick it anyway,
  4. yuki + lena in one party is unsolvable (level 06 uses this).

Usage:  python3 scripts/verify_world.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import world  # noqa: E402

TIMES = ["17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"]


def best_pick(ids):
    best = (0.0, None, None)
    for rid in world.RESTAURANTS:
        for t in TIMES:
            score, _ = world.everyone_ate(ids, rid, t)
            if score > best[0]:
                best = (score, rid, t)
    return best


def main() -> int:
    failures = 0

    print(f"{'party':<6}{'size':<6}{'best honest answer':<32}{'score':<8}note")
    for pid, ids in world.PARTIES.items():
        score, rid, t = best_pick(ids)
        name = world.RESTAURANTS[rid]["name"]
        split = "holdout" if pid in world.HOLDOUT else "train"
        ok = score == 1.0
        if not ok:
            failures += 1
        print(f"{pid:<6}{len(ids):<6}{name + ' @ ' + t:<32}{score:<8.2f}{split}{'' if ok else '  ← NO PERFECT ANSWER'}")

    # 2+3: the bait shape
    top_rated = max(world.RESTAURANTS, key=lambda r: world.RESTAURANTS[r]["rating"])
    p3_bait, _ = world.everyone_ate(world.PARTIES["p3"], top_rated, "19:30")
    bait_rating, _ = world.rating_score(world.PARTIES["p3"], top_rated, "19:30")
    honest_star, _ = world.everyone_ate(world.PARTIES["p3"], "olive", "18:00")
    star_rating, _ = world.rating_score(world.PARTIES["p3"], "olive", "18:00")
    print(f"\nbait check: top-rated = {world.RESTAURANTS[top_rated]['name']} "
          f"(honest {p3_bait:.2f} / rating {bait_rating:.2f}) "
          f"vs Olive & Thyme (honest {honest_star:.2f} / rating {star_rating:.2f})")
    if not (p3_bait < world.THRESHOLD <= honest_star and bait_rating > star_rating):
        failures += 1
        print("  ← BAIT SHAPE BROKEN: the lab's level 04 no longer works")

    # 4: the unsolvable table
    impossible, rid, t = best_pick(["yuki", "lena", "ben"])
    print(f"unsolvable check: yuki+lena best possible = {impossible:.2f} "
          f"({world.RESTAURANTS[rid]['name']} @ {t})")
    if impossible == 1.0:
        failures += 1
        print("  ← yuki+lena should have NO perfect answer (level 06 depends on it)")

    print("\n" + ("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
