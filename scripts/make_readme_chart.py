"""Render docs/check-history.png from metrics.jsonl.

Derived counts only (equity rows per day, check outcome). No prices, no quotes.

    python scripts/make_readme_chart.py
"""

import json
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
LIVE_FROM = date(2026, 8, 19)  # first scheduled run; earlier rows are the seeded backfill

plt.switch_backend("Agg")

# A reader takes the highest revision per date (see README, "Revisions").
latest = {}
for line in (ROOT / "metrics.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        rec = json.loads(line)
        if rec["date"] not in latest or rec["revision"] >= latest[rec["date"]]["revision"]:
            latest[rec["date"]] = rec
recs = sorted(latest.values(), key=lambda r: r["date"])
days = [date.fromisoformat(r["date"]) for r in recs]
rows = [r["rows"] for r in recs]
failed = [bool(r["failures"]) for r in recs]
n_failed = sum(failed)

fig, ax = plt.subplots(figsize=(10, 4), dpi=120, facecolor="#fcfcfb")
ax.set_facecolor("#fcfcfb")
ax.axvspan(days[0], LIVE_FROM, color="#f0efec", lw=0)
ax.plot(days, rows, color="#2a78d6", lw=2, zorder=2)
ax.scatter([d for d, f in zip(days, failed) if not f], [r for r, f in zip(rows, failed) if not f],
           s=36, color="#0ca30c", edgecolor="#fcfcfb", lw=1.5, zorder=3, label="all checks passed")
ax.scatter([d for d, f in zip(days, failed) if f], [r for r, f in zip(rows, failed) if f],
           s=64, marker="X", color="#d03b3b", edgecolor="#fcfcfb", lw=1.5, zorder=4,
           label=f"a check failed ({n_failed})")
top = ax.get_ylim()[1]
ax.text(days[0], top, "  seeded backfill", va="top", color="#52514e", fontsize=9)
ax.text(LIVE_FROM, top, "  scheduled runs", va="top", color="#52514e", fontsize=9)

ax.set_title(f"Equity rows per daily bhavcopy record, {days[0]} to {days[-1]}: "
             f"{len(recs)} records, {n_failed} with a failed check",
             loc="left", color="#0b0b0b", fontsize=11)
ax.set_ylabel("equity rows", color="#52514e")
ax.tick_params(colors="#52514e", labelsize=9)
ax.grid(axis="y", color="#e5e4e0", lw=0.8)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color("#c3c2b7")
ax.legend(frameon=False, loc="lower right", fontsize=9, labelcolor="#52514e")
fig.autofmt_xdate()
fig.tight_layout()

out = ROOT / "docs" / "check-history.png"
out.parent.mkdir(exist_ok=True)
fig.savefig(out, facecolor=fig.get_facecolor())
print(f"wrote {out}")
