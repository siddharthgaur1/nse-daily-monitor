# nse-daily-monitor

A daily data-quality check on the NSE equity bhavcopy, running on a schedule
since August 2026.

Every weekday it fetches the day's file through
[nse-warehouse](https://github.com/siddharthgaur1/nse-warehouse), measures it,
compares the measurements against the trailing sixty days of its own history,
and appends a record to `metrics.jsonl`. When a check fails it opens an issue
against this repository with the failing assertion.

**No exchange data is redistributed.** `metrics.jsonl` holds derived counts and
rates only -- row and symbol totals, null rates, bound-violation counts, breadth
-- never a reconstructable quote. That is a deliberate constraint inherited from
nse-warehouse, not an oversight.

## What it checks

| Check | Fails when |
|---|---|
| Publish integrity | NSE served a file that parsed to zero equity rows |
| OHLC bounds | `high < low`, or high below open/close, or low above them |
| Null close rate | above 1% of rows |
| Breadth | symbol count below half the trailing median -- a truncated file |

Holidays are not failures: NSE returns 404 and the run exits clean. A network
refusal exits 75 and the second cron of the day retries rather than filing a
false alarm.

## Revisions

Records are keyed on `(date, revision)`. If NSE republishes a corrected
bhavcopy after the day's run, `python monitor.py <date> --force` re-downloads
it and appends a new revision rather than editing the original. The file stays
append-only; a reader takes the highest revision for a date.

## Commits here are from a bot

The daily metrics commits are authored by `github-actions[bot]`, so they do not
appear on anyone's contribution graph. That is deliberate. The evidence this
repo offers is the [Actions run history](../../actions) and the append-only
`metrics.jsonl` -- both of which stand on their own, and neither of which is
improved by attributing machine output to a person.

## Running it locally

```
pip install "nse-warehouse @ git+https://github.com/siddharthgaur1/nse-warehouse"
python monitor.py            # most recent weekday
python monitor.py 2026-08-18 # a specific day
python monitor.py 2026-08-18 --force  # re-measure a corrected republish
python test_monitor.py       # offline; builds its fixtures in-process
```
