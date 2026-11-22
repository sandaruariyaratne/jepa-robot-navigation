"""Step 11 (main.py) checks: stages wire up, and a stage re-run reproduces its outputs."""

import importlib
import subprocess
import sys

import yaml

import main
from config import ROOT


def test_every_stage_module_exists():
    assert main.ORDER == ["collect", "train-numerical", "train-encoder", "train-world", "eval"]
    for stage in main.ORDER:
        for module, _ in main.STAGES[stage]:
            importlib.import_module(module if module != "evaluation" else "evaluation.__main__")


def test_strip_timing():
    obj = {"a": 1, "ms": 3.2, "plans": [{"ms": 1.0, "cost": 2}], "nested": {"ms": 0, "x": [1], "mean_plan_ms": 0.3}}
    assert main._strip_timing(obj) == {"a": 1, "plans": [{"cost": 2}], "nested": {"x": [1]}}


def _tmp_config(tmp_path, episodes=6):
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cfg["data"]["episodes"] = episodes
    cfg["data"]["path"] = str(tmp_path / "t.npz")
    cfg["data"]["splits_path"] = str(tmp_path / "s.json")
    cfg["evaluation"]["results_dir"] = str(tmp_path / "results")
    for k in ("numerical", "encoder", "predictor"):
        cfg[k]["checkpoint"] = str(tmp_path / f"{k}.pt")
        cfg[k]["metrics"] = str(tmp_path / f"{k}.json")
    cfg["encoder"]["decoder_checkpoint"] = str(tmp_path / "decoder.pt")
    cfg["imagination"]["metrics"] = str(tmp_path / "graph.json")
    cfg["planning"]["metrics"] = str(tmp_path / "planning.json")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


def test_fingerprint_reports_missing_outputs(tmp_path):
    fp = main.fingerprint(_tmp_config(tmp_path))
    assert len(fp) == 13 and set(fp.values()) == {"missing"}


def test_collect_stage_is_reproducible(tmp_path):
    cfg_path = _tmp_config(tmp_path)
    cmd = [sys.executable, "main.py", "collect", "--config", str(cfg_path)]
    hashes = []
    for _ in range(2):
        # 6 episodes cannot cover all 100 pairs, so collect exits 1 after writing its files.
        subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        fp = main.fingerprint(cfg_path)
        hashes.append((fp[str(tmp_path / "t.npz")], fp[str(tmp_path / "s.json")]))
    assert "missing" not in hashes[0] and hashes[0] == hashes[1]
