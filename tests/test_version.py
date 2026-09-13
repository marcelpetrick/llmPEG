from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from llmpeg import __version__
from llmpeg.artifact import CODEC_VERSION, FormatHeader
from prototypeWebUI import server as web

REPO = Path(__file__).resolve().parent.parent


def test_every_runtime_version_comes_from_one_source() -> None:
    assert version("llmpeg") == __version__
    assert __version__ == CODEC_VERSION
    assert FormatHeader().encoder == f"llmpeg/{__version__}"
    assert web.Handler.server_version == f"llmPEGPrototype/{__version__}"


def test_documented_examples_name_the_current_version() -> None:
    """Docs cannot import the version, so a bump that misses them fails here instead."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    format_spec = (REPO / "docs" / "format.md").read_text(encoding="utf-8")
    for text in (readme, format_spec):
        assert f'"encoder":"llmpeg/{__version__}"' in text
        assert f"written by: llmpeg/{__version__}" in text
    assert f"releases/tag/v{__version__}" in readme
    assert f"llmpeg-{__version__}-py3-none-any.whl" in readme
