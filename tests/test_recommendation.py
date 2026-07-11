from brewtrace.models import BrewLog, BrewMethod, Direction, TasteDefect, Variable, parse_brew_log
from brewtrace.tools.recommendation import diagnose, recommend


def _rec_for(text: str):
    brew = parse_brew_log(text)
    return recommend(brew, diagnose(brew)), brew


# --- One case per rule-table row -------------------------------------------


def test_sour_thin_gets_finer_grind():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00 drawdown, sour and thin")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.FINER
    assert rec.confidence == "high"


def test_sour_gets_finer_grind():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, tastes sour")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.FINER


def test_bitter_astringent_gets_coarser():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, bitter and astringent")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.COARSER


def test_bitter_gets_coarser():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, harsh and bitter")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.COARSER


def test_weak_balanced_gets_ratio_not_grind():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, weak and watery")
    assert rec.adjustment.variable == Variable.RATIO
    assert rec.adjustment.direction == Direction.DECREASE


def test_strong_muddy_gets_ratio_increase():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, heavy and muddy")
    assert rec.adjustment.variable == Variable.RATIO
    assert rec.adjustment.direction == Direction.INCREASE


def test_hollow_gets_pour_technique():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, flat and lacks sweetness")
    assert rec.adjustment.variable == Variable.POUR_TECHNIQUE
    assert rec.adjustment.direction == Direction.MORE_EVEN


def test_balanced_gets_no_change():
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, tastes great")
    assert rec.adjustment.variable == Variable.NONE
    assert rec.adjustment.direction == Direction.KEEP


def test_stalled_no_defect_gets_coarser():
    rec, _ = _rec_for("16g/250g v60, 94C, 5:30 drawdown")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.COARSER


def test_fast_drawdown_sour_gets_finer():
    rec, _ = _rec_for("16g/250g v60, 94C, 1:45 drawdown, sour")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.FINER


# --- Guards (the showcase interactions) -------------------------------------


def test_sour_thin_with_stall_flips_to_temperature():
    """The showcase case: sour + stalled drawdown must NOT get 'finer'."""
    rec, _ = _rec_for("16g/250g v60, 92C, 5:00 drawdown, sour and thin")
    assert rec.adjustment.variable == Variable.TEMPERATURE
    assert rec.adjustment.direction == Direction.INCREASE
    # The skipped grind rule must be visible as an alternative with the reason.
    assert any(a.variable == Variable.GRIND and "skipped" in a.rationale for a in rec.alternatives)


def test_sour_thin_stalled_and_temp_at_ceiling_falls_to_bloom():
    rec, _ = _rec_for("16g/250g v60, 96C, 5:00 drawdown, sour and thin")
    assert rec.adjustment.variable == Variable.BLOOM


def test_bitter_at_temp_floor_skips_temperature():
    brew = BrewLog(
        method=BrewMethod.V60,
        dose_g=16,
        water_g=250,
        temperature_c=88,
        drawdown_s=180,
        defect=TasteDefect.BITTER,
    )
    diagnosis = diagnose(brew)
    rec = recommend(brew, diagnosis)
    # First rule (coarser grind) still wins; the temp rule must be a skipped alternative.
    assert rec.adjustment.variable == Variable.GRIND
    assert any(
        a.variable == Variable.TEMPERATURE and "skipped" in a.rationale for a in rec.alternatives
    )


def test_bitter_with_stall_treats_stall_first():
    rec, _ = _rec_for("16g/250g v60, 94C, 5:30 drawdown, bitter")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.adjustment.direction == Direction.COARSER


# --- Missing-data behavior ---------------------------------------------------


def test_missing_drawdown_reduces_confidence():
    rec, _ = _rec_for("16g/250g v60, 94C, sour and thin")
    assert rec.adjustment.variable == Variable.GRIND
    assert rec.confidence == "medium"
    assert "drawdown time" in rec.adjustment.rationale


def test_no_defect_no_timing_asks_for_detail():
    rec, _ = _rec_for("16g/250g v60 at 94C")
    assert rec.adjustment.variable == Variable.NONE
    assert rec.confidence == "low"


def test_exactly_one_variable_changed():
    """Structural invariant: a recommendation is always a single adjustment."""
    rec, _ = _rec_for("16g/250g v60, 94C, 3:00, sour and thin")
    assert rec.adjustment is not None
    assert isinstance(rec.alternatives, list)
