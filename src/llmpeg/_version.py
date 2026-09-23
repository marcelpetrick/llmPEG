"""The single source of the llmPEG release version.

Packaging metadata, the artifact header's `encoder` field, and the prototype server all read
this value; `tests/test_version.py` fails when anything else falls out of step with it.
"""

__version__ = "0.5.1"
