"""Daily NSE data-quality monitor.

Fetches one trading day's bhavcopy through nse-warehouse, measures it, compares
the result against this repo's own trailing metrics history, and appends the
record. No exchange data is redistributed -- only derived counts and rates are
committed, which is what keeps this consistent with nse-warehouse's README.

The history file is the baseline. That is why there is no warehouse build in CI
and no second copy of the quality suite: one day's file plus sixty days of
committed numbers is enough to catch a truncated or malformed publish.

Exit codes:
    0   healthy, or nothing published (holiday), or already recorded
    1   a check failed -- the workflow opens an issue
    75  source unavailable (EX_TEMPFAIL) -- the later cron run retries
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from nse_warehouse.build import read_zip
from nse_warehouse.fetch import Downloader

METRICS = Path("metrics.jsonl")
DATA = Path("data")

WINDOW = 60             # trailing records used as the baseline
BREADTH_FLOOR = 0.5     # symbol count under this fraction of the median = truncated file
NULL_CLOSE_CEILING = 0.01

EX_TEMPFAIL = 75


def _ohlc_broken(bar) -> bool:
    """Same rule as nse_warehouse.quality.ohlc_consistency, one bar at a time."""
    if bar.high is None or bar.low is None:
        return False
    hi_o = bar.open if bar.open is not None else bar.high
    hi_c = bar.close if bar.close is not None else bar.high
    lo_o = bar.open if bar.open is not None else bar.low
    lo_c = bar.close if bar.close is not None else bar.low
    return bar.high < bar.low or bar.high < max(hi_o, hi_c) or bar.low > min(lo_o, lo_c)


def measure(day: date, bars) -> dict:
    """Derived metrics for one day. Nothing here reproduces a row of source data."""
    n = len(bars)
    moved = [b for b in bars if b.close is not None and b.prev_close]
    return {
        "date": day.isoformat(),
        "rows": n,
        "symbols": len({b.symbol for b in bars}),
        "series": len({b.series for b in bars}),
        "null_close_rate": round(sum(b.close is None for b in bars) / n, 6) if n else 0.0,
        "null_volume_rate": round(sum(b.volume is None for b in bars) / n, 6) if n else 0.0,
        "null_isin_rate": round(sum(b.isin is None for b in bars) / n, 6) if n else 0.0,
        "ohlc_violations": sum(_ohlc_broken(b) for b in bars),
        "zero_volume_with_turnover": sum(
            not b.volume and bool(b.turnover) for b in bars
        ),
        "turnover": round(sum(b.turnover or 0.0 for b in bars), 2),
        "advances": sum(b.close > b.prev_close for b in moved),
        "declines": sum(b.close < b.prev_close for b in moved),
    }


def compare(current: dict, history: list[dict]) -> list[str]:
    """Failure descriptions. Empty list means healthy."""
    failures = []
    if current["rows"] == 0:
        failures.append("NSE published a file that parsed to zero equity rows")
    if current["ohlc_violations"]:
        failures.append(f"{current['ohlc_violations']} bars violate OHLC bounds")
    if current["null_close_rate"] > NULL_CLOSE_CEILING:
        failures.append(
            f"null close rate {current['null_close_rate']:.2%} exceeds "
            f"{NULL_CLOSE_CEILING:.0%}"
        )

    # ponytail: trailing median only. PSI/KS on the return distribution if a
    # subtler drift than "the file is half missing" ever turns out to matter.
    baseline = [h["symbols"] for h in history[-WINDOW:] if h.get("symbols")]
    if len(baseline) >= 5:
        median = statistics.median(baseline)
        if current["symbols"] < median * BREADTH_FLOOR:
            failures.append(
                f"symbol count {current['symbols']} is below half the trailing "
                f"median of {median:.0f} -- likely a truncated file"
            )
    return failures


def _history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _default_day() -> date:
    """Today if it is a weekday, else the most recent Friday."""
    day = date.today()
    while day.weekday() > 4:
        day -= timedelta(days=1)
    return day


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    day = date.fromisoformat(argv[0]) if argv else _default_day()

    history = _history(METRICS)
    if any(h["date"] == day.isoformat() for h in history):
        # A retry run after a failure lands here, which is what stops the second
        # cron of the day from filing a duplicate issue.
        print(f"{day}: already recorded")
        return 0

    try:
        path = Downloader(DATA).fetch_day(day)
    except Exception as exc:  # network refusal, rate limit, exhausted retries
        print(f"{day}: source unavailable -- {exc}")
        return EX_TEMPFAIL

    if path is None:
        print(f"{day}: nothing published (holiday)")
        return 0

    record = measure(day, read_zip(path))
    failures = compare(record, history)
    record["failures"] = failures

    # Written before the failure is reported, so a failing check still leaves a
    # committed record of itself. The metrics and the alert are independent.
    with METRICS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")

    print(json.dumps(record, indent=2))
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
