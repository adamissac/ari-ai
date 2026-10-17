from __future__ import annotations

from security_agents.checks import library as lib
from security_agents.checks.review_packet import main, packet, render_markdown


def test_packet_covers_every_template_with_clean_rendered_code():
    entries = packet()
    assert {e["ref"] for e in entries} == set(lib.default_library().templates)
    for entry in entries:
        assert entry["imports_within_allowlist"], entry["imports"]
        assert entry["forbidden_tokens_found"] == []
        assert len(entry["renderer_sha256"]) == 64 and len(entry["rendered_sha256"]) == 64


def test_packet_hashes_are_stable_and_change_with_the_renderer(monkeypatch):
    first = {e["ref"]: e["renderer_sha256"] for e in packet()}
    assert first == {e["ref"]: e["renderer_sha256"] for e in packet()}
    monkeypatch.setattr(lib, "_PREAMBLE", lib._PREAMBLE + "\n# changed\n")
    changed = {e["ref"]: e["renderer_sha256"] for e in packet()}
    assert all(changed[ref] != first[ref] for ref in first)


def test_markdown_lists_the_checklist_and_pending_signoff(tmp_path):
    text = render_markdown(packet())
    assert "- [ ] The rendered module imports only" in text
    assert "security-owner:pending-human-signoff" in text
    out = tmp_path / "packet.md"
    assert main(["--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == text


def test_committed_review_packet_matches_the_current_renderers():
    from pathlib import Path

    committed = Path(__file__).resolve().parents[2] / "docs" / "security" / "CHECK_TEMPLATE_REVIEW.md"
    assert committed.read_text(encoding="utf-8") == render_markdown(packet()), (
        "regenerate: .venv/bin/python -m security_agents.checks.review_packet --out ../docs/security/CHECK_TEMPLATE_REVIEW.md"
    )
