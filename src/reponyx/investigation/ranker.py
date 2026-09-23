"""Evidence classification and ranking for investigation reports."""

from __future__ import annotations

import re
from collections.abc import Sequence

from reponyx.investigation.models import (
    ClassifiedEvidenceItem,
    Evidence,
    EvidenceCategory,
)

_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
        "and", "or", "but", "not", "with", "by", "from", "as", "this", "that",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may", "can",
        "shall", "might", "must", "need", "returns", "value", "values",
        "expected", "actual", "when", "how", "what", "why", "where", "which",
        "who", "whom", "their", "there", "they", "them", "then", "than",
        "these", "those", "no", "use", "uses", "using", "used",
    }
)


def _extract_issue_terms(issue: str) -> list[str]:
    words = re.findall(r"[a-z]+", issue.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _is_test_file(file_path: str) -> bool:
    fp_lower = file_path.lower()
    return "test" in fp_lower or "spec" in fp_lower


def _term_match_score(file_path: str, symbol: str | None, key_terms: list[str]) -> float:
    fp_lower = file_path.lower()
    sym_lower = (symbol or "").lower()
    matches = sum(1 for t in key_terms if len(t) > 2 and (t in fp_lower or t in sym_lower))
    if not key_terms:
        return 0.0
    return min(1.0, matches / max(len([t for t in key_terms if len(t) > 2]), 1))


def _symbol_reference_score(
    evidence_item: Evidence,
    all_evidence: Sequence[Evidence],
    key_terms: list[str],
) -> float:
    score = 0.0
    fp = (evidence_item.file_path or "").lower()
    sym = (evidence_item.symbol or "").lower()
    for other in all_evidence:
        if other.evidence_id == evidence_item.evidence_id:
            continue
        other_content = (other.description or "").lower()
        if sym and sym in other_content:
            score += 0.3
        other_ref = (other.source_reference or "").lower()
        if sym and sym in other_ref:
            score += 0.2
    return min(1.0, score)


def classify_evidence(
    evidence: Sequence[Evidence],
    issue: str,
) -> list[ClassifiedEvidenceItem]:
    key_terms = _extract_issue_terms(issue)
    classified: list[ClassifiedEvidenceItem] = []

    for item in evidence:
        fp = item.file_path or ""
        sym = item.symbol
        is_test = _is_test_file(fp)
        term_score = _term_match_score(fp, sym, key_terms)
        ref_score = _symbol_reference_score(item, evidence, key_terms)
        combined_score = min(1.0, term_score * 0.7 + ref_score * 0.3)

        if is_test and term_score > 0.0:
            category = EvidenceCategory.PRIMARY_TESTS
            reason = f"Test file with {term_score:.0%} term match"
        elif not is_test and item.type == "source_code" and sym:
            category = EvidenceCategory.DIRECT_REFERENCES
            reason = "Source-inspected implementation with symbol"
        elif not is_test and term_score > 0.0:
            category = EvidenceCategory.PRIMARY_IMPLEMENTATION
            reason = f"Implementation file with {term_score:.0%} term match"
        elif combined_score > 0.1:
            category = EvidenceCategory.SUPPORTING
            reason = f"Supporting evidence with {combined_score:.0%} relevance"
        else:
            category = EvidenceCategory.UNRELATED
            reason = "No matching terms or symbols"

        classified.append(
            ClassifiedEvidenceItem(
                evidence_id=item.evidence_id,
                category=category,
                file_path=fp,
                symbol=sym,
                relevance_score=round(combined_score, 3),
                reason=reason,
            )
        )

    classified.sort(key=lambda c: (c.category.value, -c.relevance_score))
    return classified
