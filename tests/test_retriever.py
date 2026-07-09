from brewtrace.tools.recipe_retriever import load_corpus, search


def test_corpus_loads_all_files():
    chunks = load_corpus()
    sources = {c.source for c in chunks}
    assert sources == {"v60.md", "kalita.md", "clever.md", "troubleshooting.md"}


def test_chunks_split_on_headings():
    chunks = load_corpus()
    v60_headings = {c.heading for c in chunks if c.source == "v60.md"}
    assert "Grind" in v60_headings
    assert "Drawdown" in v60_headings


def test_search_sour_thin_finds_defect_notes():
    results = search("v60 sour thin underextraction", k=3)
    assert results
    top_texts = " ".join(c.text.lower() for c, _ in results)
    assert "finer" in top_texts


def test_search_stall_finds_stall_guidance():
    results = search("stalled drawdown clogged filter", k=3)
    top_texts = " ".join(c.text.lower() for c, _ in results)
    assert "coarser" in top_texts


def test_search_no_match_returns_empty():
    assert search("quantum flux capacitor", k=3) == []


def test_search_respects_k():
    assert len(search("grind", k=2)) <= 2
