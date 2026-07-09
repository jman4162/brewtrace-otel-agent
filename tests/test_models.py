from brewtrace.models import BrewMethod, TasteDefect, parse_brew_log


def test_canonical_prompt():
    brew = parse_brew_log(
        "I brewed 16g coffee / 250g water, V60, 94C, 3:45 drawdown, sour and thin"
    )
    assert brew.method == BrewMethod.V60
    assert brew.dose_g == 16
    assert brew.water_g == 250
    assert brew.temperature_c == 94
    assert brew.drawdown_s == 225
    assert brew.defect == TasteDefect.SOUR_THIN
    assert brew.ratio == 15.62


def test_compact_format():
    brew = parse_brew_log("16g/250g V60, 94°C, 3:45, sour and thin")
    assert brew.dose_g == 16
    assert brew.water_g == 250
    assert brew.defect == TasteDefect.SOUR_THIN


def test_thin_and_sour_reversed_order():
    brew = parse_brew_log("15g/240g kalita, tasted thin and kind of sour")
    assert brew.method == BrewMethod.KALITA
    assert brew.defect == TasteDefect.SOUR_THIN


def test_bitter_astringent():
    brew = parse_brew_log("20g/300g clever at 96C, bitter with a drying finish")
    assert brew.method == BrewMethod.CLEVER
    assert brew.defect == TasteDefect.BITTER_ASTRINGENT


def test_plain_bitter():
    assert parse_brew_log("v60, harsh and bitter").defect == TasteDefect.BITTER


def test_plain_sour():
    assert parse_brew_log("v60 came out sour").defect == TasteDefect.SOUR


def test_weak():
    assert parse_brew_log("tastes watery and weak, otherwise fine").defect == TasteDefect.WEAK


def test_hollow():
    assert parse_brew_log("kind of flat, lacks sweetness").defect == TasteDefect.HOLLOW


def test_balanced():
    assert parse_brew_log("16g/250g v60, tastes great").defect == TasteDefect.BALANCED


def test_partial_input_no_temp_no_time():
    brew = parse_brew_log("16g/250g v60, sour")
    assert brew.temperature_c is None
    assert brew.drawdown_s is None
    assert brew.defect == TasteDefect.SOUR


def test_no_defect():
    brew = parse_brew_log("16g/250g v60 at 94C")
    assert brew.defect is None


def test_explicit_dose_water_labels():
    brew = parse_brew_log("30g coffee with 500g water in the kalita")
    assert brew.dose_g == 30
    assert brew.water_g == 500


def test_grind_setting_extraction():
    brew = parse_brew_log("16g/250g v60, Ode at 5.2, sour")
    assert brew.grind_setting == "5.2"


def test_ratio_none_when_missing_water():
    brew = parse_brew_log("16g dose v60, sour")
    assert brew.ratio is None
