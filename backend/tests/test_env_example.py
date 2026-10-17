""".env.example is consumed verbatim by Compose ``env_file``, which does not strip an inline
comment after an EMPTY value: ``KEY=   # note`` becomes the value ``# note`` (it silently set
AGENT_MODEL_OVERRIDES to ``# e.g. scout=<model>`` and broke the compose stack once the RL pin
was added). Keep comments on their own lines for empty keys, and keep the file loadable."""

from __future__ import annotations

import re
from pathlib import Path

from backend.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_no_inline_comment_after_an_empty_value() -> None:
    bad = [
        f"{n}: {line}"
        for n, line in enumerate(ENV_EXAMPLE.read_text().splitlines(), 1)
        if re.match(r"^[A-Z0-9_]+=\s+#", line)
    ]
    assert not bad, bad


def test_env_example_values_load_as_settings(monkeypatch) -> None:
    for line in ENV_EXAMPLE.read_text().splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
        if not m:
            continue
        value = re.sub(r"\s+#.*$", "", m.group(2)).strip()  # Compose: comment after a value
        monkeypatch.setenv(m.group(1), value)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.rl_checkpoint_sha256 is None and s.agent_model_overrides.strip() == ""
