"""The judge module must degrade cleanly when the optional extra is absent."""

import builtins

from brewtrace.evals import judge


def test_judge_without_extra_returns_2(monkeypatch, capsys):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("strands_evals"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert judge.main([]) == 2
    assert "uv sync --extra judge" in capsys.readouterr().out
