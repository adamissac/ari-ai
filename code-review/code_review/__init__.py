"""Pillar 1: the reviewer/repair runtime agent (``AgentName.reviewer``).

Public entry points live in :mod:`code_review.api`. Everything here runs through the
backend ``AssessmentHost`` and LLM gateway; repository content is untrusted data.
"""

PROMPT_VERSION = "reviewer@1"
REPAIR_PROMPT_VERSION = "reviewer-repair@1"
