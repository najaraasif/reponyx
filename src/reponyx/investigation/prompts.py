"""Versioned prompts for structured investigation stages."""

PROMPT_VERSION = "phase3-v1"

PLANNER_PROMPT = """You are planning a read-only software investigation.
Return concise ordered investigation steps and retrieval queries. Do not propose edits or commands.
Issue: {issue}
Repository map: {repository_map}
"""

HYPOTHESIS_PROMPT = """You are generating software investigation hypotheses.
Separate observed evidence from hypotheses. Use only supplied source-attributed evidence.
Issue: {issue}
Evidence: {evidence}
"""

VERIFIER_PROMPT = """You are verifying hypotheses using only supplied read-only repository evidence.
 Mark each hypothesis supported, contradicted, or inconclusive. Never invent paths, lines, or
 runtime behavior.
Hypotheses: {hypotheses}
Evidence: {evidence}
"""

REPORT_PROMPT = """You are writing a concise root-cause investigation report.
Do not claim a fix, test execution, runtime behavior, or certainty not represented by evidence.
Issue: {issue}
Hypotheses: {hypotheses}
Evidence: {evidence}
"""
