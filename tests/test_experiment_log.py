from brewtrace.models import (
    Adjustment,
    BrewLog,
    BrewMethod,
    Direction,
    Recommendation,
    TasteDefect,
    Variable,
)
from brewtrace.tools.experiment_log import log_experiment, recent_experiments


def _sample():
    brew = BrewLog(
        method=BrewMethod.V60,
        dose_g=16,
        water_g=250,
        temperature_c=94,
        drawdown_s=225,
        defect=TasteDefect.SOUR_THIN,
        raw_text="16g/250g v60 sour and thin",
    )
    rec = Recommendation(
        adjustment=Adjustment(
            variable=Variable.GRIND,
            direction=Direction.FINER,
            magnitude="one step",
            rationale="underextraction",
        ),
        confidence="high",
    )
    return brew, rec


def test_log_and_read_back(tmp_path):
    db = tmp_path / "test.db"
    brew, rec = _sample()
    row_id = log_experiment(brew, rec, db_path=db)
    assert row_id == 1

    rows = recent_experiments(db_path=db)
    assert len(rows) == 1
    assert rows[0]["defect"] == "sour_thin"
    assert rows[0]["variable"] == "grind"
    assert rows[0]["direction"] == "finer"
    assert rows[0]["brew"]["dose_g"] == 16


def test_recent_orders_newest_first(tmp_path):
    db = tmp_path / "test.db"
    brew, rec = _sample()
    log_experiment(brew, rec, db_path=db)
    log_experiment(brew, rec, db_path=db)
    rows = recent_experiments(limit=2, db_path=db)
    assert [r["id"] for r in rows] == [2, 1]


def test_recent_respects_limit(tmp_path):
    db = tmp_path / "test.db"
    brew, rec = _sample()
    for _ in range(4):
        log_experiment(brew, rec, db_path=db)
    assert len(recent_experiments(limit=2, db_path=db)) == 2
