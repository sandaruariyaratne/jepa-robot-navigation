"""The browser demo (web/) is a JavaScript port of the renderer, networks, imagined graph and P2 planner.

web/test/check.mjs compares it with PyTorch on fixed layouts: frames, imagined graph and D(c)
exactly, latents and planner costs to 1e-3. Regenerate the vectors after retraining with
`python web/export_models.py`.
"""

import shutil
import subprocess

import pytest

from config import ROOT


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_javascript_port_matches_pytorch():
    r = subprocess.run(["node", str(ROOT / "web/test/check.mjs")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "all checks passed" in r.stdout
