"""The full-corpora runner (tests/corpora_run.py, #153) on a fake corpora
tree built from the committed subset: discovery for both upstream layouts,
the DOMAIN filter, the empty-directory exit, and the written report."""
import json
import os
import shutil
import time

import corpora_run
import golden
import pytest
from golden import IPC

BLOCKS = os.path.join(IPC, "blocks-strips-typed")
CRASH = os.path.join(IPC, "pipesworld-metric-time-constraints")


def fake_corpora(root):
    # potassco: one shared domain.pddl, and one domain per instance
    shared = root / "potassco" / "ipc-2000" / "domains" / "blocks"
    (shared / "instances").mkdir(parents=True)
    shutil.copy(os.path.join(BLOCKS, "domain.pddl"), shared / "domain.pddl")
    shutil.copy(os.path.join(BLOCKS, "p01.pddl"), shared / "instances" / "instance-1.pddl")
    per = root / "potassco" / "ipc-2006" / "domains" / "pipes"
    (per / "instances").mkdir(parents=True)
    (per / "domains").mkdir()
    shutil.copy(os.path.join(CRASH, "domain.pddl"), per / "domains" / "domain-1.pddl")
    shutil.copy(os.path.join(CRASH, "p01.pddl"), per / "instances" / "instance-1.pddl")
    # classical: pairs listed in api.py
    cl = root / "classical" / "classical" / "bw"
    cl.mkdir(parents=True)
    shutil.copy(os.path.join(BLOCKS, "domain.pddl"), cl / "domain.pddl")
    shutil.copy(os.path.join(BLOCKS, "p02.pddl"), cl / "p2.pddl")
    (cl / "api.py").write_text(
        "domains = [\n{'name': 'bw', 'problems': [('bw/domain.pddl', 'bw/p2.pddl')]}]\n"
    )


def run(monkeypatch, root, **env):
    monkeypatch.setenv("CORPORA_DIR", str(root))
    monkeypatch.setenv("CORPORA_JOBS", "1")
    for k in ("CORPORA_OUT", "DOMAIN", "CORPORA_TIMEOUT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return corpora_run.main()


def test_discover_both_layouts(tmp_path):
    fake_corpora(tmp_path)
    pairs = corpora_run.discover(str(tmp_path), None)
    rel = [(c, os.path.relpath(d, tmp_path), os.path.relpath(p, tmp_path)) for c, d, p in pairs]
    assert rel == [
        ("classical", "classical/classical/bw/domain.pddl", "classical/classical/bw/p2.pddl"),
        ("potassco", "potassco/ipc-2000/domains/blocks/domain.pddl",
         "potassco/ipc-2000/domains/blocks/instances/instance-1.pddl"),
        ("potassco", "potassco/ipc-2006/domains/pipes/domains/domain-1.pddl",
         "potassco/ipc-2006/domains/pipes/instances/instance-1.pddl"),
    ]
    assert len(corpora_run.discover(str(tmp_path), "pipes")) == 1


def test_per_domain_sampling(tmp_path, monkeypatch):
    """CORPORA_PER_DOMAIN keeps the first N problems per variant, in natural
    order (instance-2 before instance-10)."""
    fake_corpora(tmp_path)
    inst = tmp_path / "potassco" / "ipc-2000" / "domains" / "blocks" / "instances"
    for n in (10, 2):
        shutil.copy(inst / "instance-1.pddl", inst / ("instance-%d.pddl" % n))
    monkeypatch.setenv("CORPORA_PER_DOMAIN", "2")
    pairs = corpora_run.discover(str(tmp_path), "blocks", corpora_run.per_domain())
    assert [os.path.basename(p) for _, _, p in pairs] == ["instance-1.pddl", "instance-2.pddl"]
    monkeypatch.setenv("CORPORA_PER_DOMAIN", "0")
    assert corpora_run.per_domain() is None
    assert len(corpora_run.discover(str(tmp_path), None, 1)) == 3


def test_empty_corpora_exits_zero(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, tmp_path / "missing") == 0
    assert "no domain/problem pairs" in capsys.readouterr().out


def test_report(tmp_path, monkeypatch):
    fake_corpora(tmp_path)
    assert run(monkeypatch, tmp_path) == 0
    out = tmp_path / "results"
    summary = json.loads((out / "summary.json").read_text())
    # blocks-strips-typed reports an undeclared predicate; pipesworld crashes (#140)
    assert summary == {"classical": {"issues": 1}, "potassco": {"crash": 1, "issues": 1}}
    snap = json.loads(
        (out / "potassco/ipc-2006/domains/pipes/instances/instance-1.json").read_text()
    )
    assert snap["error"]["type"] == "IndexError"
    assert snap["domain"] == "potassco/ipc-2006/domains/pipes/domains/domain-1.pddl"


def slow(*args):
    time.sleep(5)


@pytest.mark.parametrize("stage", ["DomainProblem", "diagnose"])
def test_timeout_escapes_snapshot(tmp_path, monkeypatch, stage):
    """The deadline must cut through snapshot()'s own exception handlers,
    whether loading or validation is slow (review on #154)."""
    fake_corpora(tmp_path)
    monkeypatch.setattr(golden, stage, slow)
    start = time.monotonic()
    out = tmp_path / "o"
    assert run(monkeypatch, tmp_path, DOMAIN="blocks", CORPORA_OUT=str(out),
               CORPORA_TIMEOUT="1") == 0
    assert time.monotonic() - start < 3
    summary = json.loads((out / "summary.json").read_text())
    assert summary == {"potassco": {"timeout": 1}}
    snap = json.loads((out / "potassco/ipc-2000/domains/blocks/instances/instance-1.json")
                      .read_text())
    assert snap["timeout"] == 1 and "error" not in snap
