"""The two-second version of reward hacking — no API calls, no model.

The same party, two fixed decisions, both judges. Run it:

    python3 hack_2sec.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world  # noqa: E402

PARTY = "p3"
PICKS = [
    ("CAREFUL", "olive", "18:00"),   # the table answer
    ("HACKED", "smoke", "19:30"),    # the ratings answer
]


def main():
    ids = world.PARTIES[PARTY]
    roster = " · ".join(f"{world.PEOPLE[i]['name']} ({world.PEOPLE[i]['label']})" for i in ids)
    print(f"Same party ({roster}), two picks, two judges:\n")

    print(f"  {'':<10}{'everyone_ate':<16}{'rating_score':<14}")
    rows = []
    for tag, rid, t in PICKS:
        honest, seats = world.everyone_ate(ids, rid, t)
        gameable, _ = world.rating_score(ids, rid, t)
        rows.append((tag, rid, t, honest, seats, gameable))
        print(f"  {tag:<10}{honest:<16.2f}{gameable:<14.2f}"
              f"{world.RESTAURANTS[rid]['name']} @ {t}")

    print("\nWhat each judge 'sees':")
    _, rid, t, honest, seats, _ = rows[1]
    for s in seats:
        if not s["ate"]:
            print(f"  - {s['name']}: {s['why']}")
    print("  The rating judge cannot see any of that. It reads one field:")
    print("      def rating_score(party, pick):")
    print("          return pick.rating / 5.0     # <- party is never used")
    print("\nAn optimizer pointed at rating_score will learn HACKED. That is not a bug.")


if __name__ == "__main__":
    main()
