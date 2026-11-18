"""The approval list: every planned moment, numbered, so the owner can say yes or no to each.

  python moments.py --work W list            # prints the table + writes W/review/moments.md
  python moments.py --work W skip 3 7        # turn moments off
  python moments.py --work W keep 3          # turn a moment back on
  python moments.py --work W family broll off # switch a whole family off: broll | animations | graphics

Families: broll = B-roll cutaways; animations = kinetic words; graphics = motion-graphic pages
(stats, lists, titles, UI mockups...). Skipped moments stay in beats.json (marked "skip") so they
can be brought back without re-planning.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import load_json, save_json


def family(b):
    if b.get("type") == "words":
        return "animations"
    return "broll" if b.get("kind") == "broll" else "graphics"


def describe(b):
    if b.get("type") == "words":
        return " / ".join(L["text"] for L in b.get("lines", []))
    k = b.get("kind")
    if k == "broll":
        return f"{b.get('query', '')}" + (f"  [{b.get('credit', '')[:60]}]" if b.get("credit") else "")
    bits = [b.get("label") or b.get("title") or ""]
    for key in ("value", "name", "left", "text", "target", "serif"):
        if b.get(key) not in (None, ""):
            bits.append(str(b[key]))
    if b.get("items"):
        bits.append(", ".join(str(i.get("text") or i.get("name") or i.get("label")) for i in b["items"]))
    return " - ".join(x for x in bits if x)


def fmt_t(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def table(plan):
    rows = ["| # | time | family | effect | what it shows | why | on? |", "|---|---|---|---|---|---|---|"]
    for i, b in enumerate(plan["beats"]):
        eff = b.get("kind") if b.get("type") == "page" else f"words ({b.get('anim', 'mask')})"
        rows.append(f"| {i + 1} | {fmt_t(b['at'])}-{fmt_t(b['until'])} | {family(b)} | {eff} | {describe(b)} | "
                    f"{b.get('why', '')} | {'no' if b.get('skip') else 'yes'} |")
    return "\n".join(rows)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to a legacy code page
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("cmd", choices=["list", "skip", "keep", "family"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    path = os.path.join(a.work, "beats.json")
    plan = load_json(path)
    if a.cmd in ("skip", "keep"):
        for n in a.args:
            plan["beats"][int(n) - 1]["skip"] = a.cmd == "skip"
        save_json(plan, path)
    elif a.cmd == "family":  # e.g. family broll off
        fam, state = a.args[0], a.args[1].lower()
        for b in plan["beats"]:
            if family(b) == fam:
                b["skip"] = state in ("off", "no", "false")
        save_json(plan, path)
    md = table(plan)
    os.makedirs(os.path.join(a.work, "review"), exist_ok=True)
    open(os.path.join(a.work, "review", "moments.md"), "w", encoding="utf-8").write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
