"""One runnable check: python test_monitor.py"""

from types import SimpleNamespace

from monitor import _ohlc_broken, compare, measure
from datetime import date


def bar(**kw):
    base = dict(symbol="ACME", series="EQ", isin="INE000A01001", open=100.0, high=110.0,
                low=95.0, close=105.0, last=105.0, prev_close=100.0, volume=1000,
                turnover=105000.0, trades=50)
    return SimpleNamespace(**{**base, **kw})


def test_ohlc():
    assert not _ohlc_broken(bar())
    assert _ohlc_broken(bar(high=90.0))            # high below low
    assert _ohlc_broken(bar(high=104.0))           # high below close
    assert _ohlc_broken(bar(low=101.0))            # low above open
    assert not _ohlc_broken(bar(high=None))        # missing bounds are not violations
    assert not _ohlc_broken(bar(open=None, close=None))


def test_measure():
    m = measure(date(2026, 8, 19), [bar(), bar(symbol="B", close=99.0), bar(symbol="C", close=None)])
    assert m["rows"] == 3 and m["symbols"] == 3
    assert m["advances"] == 1 and m["declines"] == 1   # the null close counts as neither
    assert m["null_close_rate"] == round(1 / 3, 6)


def test_compare():
    history = [{"date": "x", "symbols": 2000} for _ in range(10)]
    full = measure(date(2026, 8, 19), [bar(symbol=f"S{i}") for i in range(1900)])
    thin = measure(date(2026, 8, 19), [bar(symbol=f"S{i}") for i in range(400)])

    assert compare(full, history) == []
    assert any("truncated" in f for f in compare(thin, history))
    assert compare(thin, history[:3]) == []   # too little history to judge breadth
    assert compare(thin, []) == []

    assert any("OHLC" in f for f in compare(measure(date(2026, 8, 19), [bar(high=90.0)]), []))
    assert any("zero equity rows" in f for f in compare(measure(date(2026, 8, 19), []), []))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
