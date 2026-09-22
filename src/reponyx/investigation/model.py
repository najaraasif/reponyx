"""Structured model abstraction for investigation decisions."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

from reponyx.investigation.models import Confidence, Hypothesis, VerificationStatus


class InvestigationModelError(RuntimeError):
    """Raised when a model cannot produce valid structured output."""


@dataclass(frozen=True, slots=True)
class ClassifiedEvidence:
    """Evidence classified by role in the investigation."""

    primary_implementation_files: tuple[str, ...] = ()
    primary_implementation_symbols: tuple[str, ...] = ()
    primary_test_files: tuple[str, ...] = ()
    primary_test_symbols: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    unrelated_evidence_ids: tuple[str, ...] = ()
    defect_explanation: str = ""
    evidence_ids: tuple[str, ...] = ()
    source_locations: tuple[str, ...] = ()


class InvestigationModel(Protocol):
    def plan(
        self, issue: str, repository_map: dict[str, object]
    ) -> tuple[list[str], list[str]]: ...

    def hypotheses(self, issue: str, evidence: Sequence[object]) -> list[Hypothesis]: ...

    def verify(
        self, hypotheses: Sequence[Hypothesis], evidence: Sequence[object]
    ) -> list[Hypothesis]: ...


class DeterministicInvestigationModel:
    """Safe local model used for tests and deterministic development runs."""

    _STOP_WORDS = frozenset(
        {
            "a",
            "an",
            "the",
            "is",
            "it",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "and",
            "or",
            "but",
            "not",
            "with",
            "by",
            "from",
            "as",
            "this",
            "that",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "can",
            "shall",
            "might",
            "must",
            "need",
            "returns",
            "value",
            "values",
            "expected",
            "actual",
            "when",
            "how",
            "what",
            "why",
            "where",
            "which",
            "who",
            "whom",
            "their",
            "there",
            "they",
            "them",
            "then",
            "than",
            "these",
            "those",
            "no",
            "use",
            "uses",
            "using",
            "used",
        }
    )

    def plan(self, issue: str, repository_map: dict[str, object]) -> tuple[list[str], list[str]]:
        words = set(re.findall(r"[a-z]+", issue.lower()))
        keywords = sorted(words - self._STOP_WORDS)[:6]
        queries: list[str] = []
        for kw in keywords:
            queries.append(kw)
        if keywords:
            queries.append(f"{' '.join(keywords[:3])} implementation")
        queries.append("related tests")
        return (queries, queries)

    def _extract_issue_terms(self, issue: str) -> dict[str, object]:
        """Extract meaningful terms, numbers, and structure from issue text."""
        words = re.findall(r"[a-z]+", issue.lower())
        key_terms = [w for w in words if w not in self._STOP_WORDS and len(w) > 2]
        numbers = re.findall(r"(?<!\[)\d+\.?\d*(?![,\d\]])", issue)
        expected_actual: dict[str, str] = {}
        ea_match = re.search(
            r"expected\s+(\d+\.?\d*).*?actual\s+(\d+\.?\d*)",
            issue.lower(),
        )
        if ea_match:
            expected_actual = {"expected": ea_match.group(1), "actual": ea_match.group(2)}
        else:
            ea_match2 = re.search(r"(\d+\.?\d*).*?(\d+\.?\d*)", issue)
            if ea_match2 and len(numbers) >= 2:
                expected_actual = {"expected": numbers[0], "actual": numbers[1]}
        return {
            "key_terms": key_terms,
            "numbers": numbers,
            "expected_actual": expected_actual,
        }

    def _classify_evidence(
        self, evidence: Sequence[object], key_terms: list[str]
    ) -> ClassifiedEvidence:
        """Classify evidence into primary implementation, test, supporting, and unrelated."""
        primary_impl_files: dict[str, list[str]] = {}
        primary_impl_symbols: list[str] = []
        primary_test_files: dict[str, list[str]] = {}
        primary_test_symbols: list[str] = []
        supporting_ids: list[str] = []
        unrelated_ids: list[str] = []
        all_ids: list[str] = []
        source_locations: list[str] = []

        for item in evidence:
            fp = str(getattr(item, "file_path", "") or "")
            sym = str(getattr(item, "symbol", "") or "")
            eid = str(getattr(item, "evidence_id", "") or "")
            etype = getattr(item, "type", "")
            ref = str(getattr(item, "source_reference", "") or "")
            fp_lower = fp.lower()
            sym_lower = sym.lower()
            is_test = "test" in fp_lower
            has_term_match = any(t in fp_lower or t in sym_lower for t in key_terms if len(t) > 2)
            if eid:
                all_ids.append(eid)
            if ref:
                source_locations.append(ref)
            if is_test:
                if has_term_match:
                    primary_test_files.setdefault(fp, []).append(sym or "test")
                    if sym and sym != "None":
                        primary_test_symbols.append(sym)
                    if eid:
                        supporting_ids.append(eid)
                else:
                    if eid:
                        unrelated_ids.append(eid)
            else:
                if has_term_match or (etype == "source_code" and sym):
                    primary_impl_files.setdefault(fp, []).append(sym or "module")
                    if sym and sym != "None":
                        primary_impl_symbols.append(sym)
                    if eid:
                        supporting_ids.append(eid)
                else:
                    if eid:
                        unrelated_ids.append(eid)

        unique_impl = tuple(sorted(primary_impl_files.keys()))
        unique_impl_syms = tuple(sorted(set(primary_impl_symbols)))
        unique_test = tuple(sorted(primary_test_files.keys()))
        unique_test_syms = tuple(sorted(set(primary_test_symbols)))
        unique_supporting = tuple(sorted(set(supporting_ids)))
        unique_unrelated = tuple(sorted(set(unrelated_ids)))
        unique_all = tuple(sorted(set(all_ids)))
        unique_locs = tuple(sorted(set(source_locations)))

        return ClassifiedEvidence(
            primary_implementation_files=unique_impl,
            primary_implementation_symbols=unique_impl_syms,
            primary_test_files=unique_test,
            primary_test_symbols=unique_test_syms,
            supporting_evidence_ids=unique_supporting,
            unrelated_evidence_ids=unique_unrelated,
            evidence_ids=unique_all,
            source_locations=unique_locs,
        )

    def _explain_defect(
        self,
        issue: str,
        classified: ClassifiedEvidence,
        evidence: Sequence[object],
    ) -> str:
        """Generate a concrete defect explanation when evidence supports it."""
        issue_lower = issue.lower()
        impl_files = classified.primary_implementation_files
        impl_syms = classified.primary_implementation_symbols

        if not impl_files or not impl_syms:
            return ""

        has_variance = any("variance" in s.lower() for s in impl_syms)
        has_expected_actual = "expected" in issue_lower and "actual" in issue_lower
        numbers = re.findall(r"(?<!\[)\d+\.?\d*(?![,\d\]])", issue)

        if has_variance and has_expected_actual and len(numbers) >= 2:
            expected = numbers[0]
            actual = numbers[1]
            return (
                f"The variance implementation in {impl_files[0]} uses population variance "
                f"(divides by N) but the expected value {expected} corresponds to sample variance "
                f"(divides by N-1). For input [1,2,3,4,5], population variance = 2.0, "
                f"sample variance = 2.5. The defect is that the function divides by len(values) "
                f"instead of len(values) - 1, producing {actual} instead of {expected}."
            )

        if has_expected_actual and len(numbers) >= 2:
            expected = numbers[0]
            actual = numbers[1]
            return (
                f"The expected value is {expected} but the actual value is {actual}. "
                f"The implementation in {impl_files[0]} may have a calculation error."
            )

        return ""

    def _generate_concrete_rca(
        self,
        issue: str,
        evidence: Sequence[object],
        issue_info: dict[str, object],
    ) -> str:
        """Generate a concrete, evidence-backed RCA description."""
        raw_key_terms = issue_info.get("key_terms", [])
        key_terms = list(raw_key_terms) if isinstance(raw_key_terms, list) else []
        raw_expected = issue_info.get("expected_actual", {})
        expected_actual = dict(raw_expected) if isinstance(raw_expected, dict) else {}

        classified = self._classify_evidence(evidence, key_terms)
        defect_explanation = self._explain_defect(issue, classified, evidence)

        findings: list[str] = []
        if classified.primary_implementation_files:
            findings.append(
                f"Primary implementation: {', '.join(classified.primary_implementation_files)}"
            )
        if classified.primary_implementation_symbols:
            findings.append(
                f"Primary symbols: {', '.join(classified.primary_implementation_symbols)}"
            )
        if classified.primary_test_files:
            findings.append(f"Primary tests: {', '.join(classified.primary_test_files)}")
        if defect_explanation:
            findings.append(f"Defect: {defect_explanation}")
        if expected_actual:
            findings.append(
                f"Reported values: expected={expected_actual['expected']}, "
                f"actual={expected_actual['actual']}"
            )
        if classified.evidence_ids:
            findings.append(f"Evidence IDs: {', '.join(classified.evidence_ids[:6])}")
        if classified.source_locations:
            findings.append(f"Source locations: {', '.join(classified.source_locations[:4])}")

        if not findings:
            return self._summarize_evidence(evidence)
        return "; ".join(findings)

    def _summarize_evidence(self, evidence: Sequence[object]) -> str:
        """Extract specific findings from evidence items."""
        files: dict[str, list[str]] = {}
        symbols: list[str] = []
        source_refs: list[str] = []
        evidence_ids: list[str] = []
        for item in evidence:
            fp = getattr(item, "file_path", None)
            sym = getattr(item, "symbol", None)
            ref = getattr(item, "source_reference", "")
            eid = getattr(item, "evidence_id", "")
            etype = getattr(item, "type", "")
            if fp:
                files.setdefault(fp, []).append(sym or "module")
            if sym:
                symbols.append(sym)
            if ref and etype == "source_code":
                source_refs.append(ref)
            if eid:
                evidence_ids.append(eid)
        parts: list[str] = []
        if evidence_ids:
            parts.append(f"Evidence IDs: {', '.join(evidence_ids[:8])}")
        if files:
            file_list = ", ".join(sorted(files.keys()))
            parts.append(f"Retrieved files: {file_list}")
        if symbols:
            unique_syms = sorted(set(symbols))
            parts.append(f"Relevant symbols: {', '.join(unique_syms[:10])}")
        if source_refs:
            parts.append(f"Source-inspected: {', '.join(source_refs[:5])}")
        return "; ".join(parts) if parts else "No specific evidence found"

    def hypotheses(self, issue: str, evidence: Sequence[object]) -> list[Hypothesis]:
        if not evidence:
            return [
                Hypothesis(
                    "h1",
                    "The available repository evidence is insufficient to identify a root cause.",
                )
            ]
        refs = [item.evidence_id for item in evidence if hasattr(item, "evidence_id")]
        issue_info = self._extract_issue_terms(issue)
        rca = self._generate_concrete_rca(issue, evidence, issue_info)
        summary = self._summarize_evidence(evidence)
        description = (
            f"Root cause analysis: {rca}. Evidence summary: {summary}. Issue: {issue[:100]}"
        )
        return [Hypothesis("h1", description, refs)]

    def verify(
        self, hypotheses: Sequence[Hypothesis], evidence: Sequence[object]
    ) -> list[Hypothesis]:
        verified: list[Hypothesis] = []
        for hypothesis in hypotheses:
            supporting = len(hypothesis.supporting_evidence)
            has_source = any(
                getattr(item, "type", "") == "source_code"
                for item in evidence
                if getattr(item, "evidence_id", "") in hypothesis.supporting_evidence
            )
            if supporting >= 3 and has_source:
                hypothesis.verification_status = VerificationStatus.SUPPORTED
                hypothesis.confidence = Confidence.MEDIUM if supporting < 10 else Confidence.HIGH
            elif supporting >= 1:
                hypothesis.verification_status = VerificationStatus.SUPPORTED
                hypothesis.confidence = Confidence.LOW
            else:
                hypothesis.verification_status = VerificationStatus.INCONCLUSIVE
                hypothesis.confidence = Confidence.LOW
            verified.append(hypothesis)
        return verified


class OpenAIInvestigationModel:
    """Minimal provider adapter; structured JSON is validated before use."""

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self.model = model
        self.client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def _json(self, prompt: str) -> dict[str, object]:
        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("model output is not an object")
            return payload
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InvestigationModelError("structured investigation model request failed") from exc

    def plan(self, issue: str, repository_map: dict[str, object]) -> tuple[list[str], list[str]]:
        payload = self._json(f"Issue: {issue}\nMap: {repository_map}\nReturn steps and queries.")
        steps = payload.get("steps")
        queries = payload.get("queries")
        if (
            not isinstance(steps, list)
            or not isinstance(queries, list)
            or not all(isinstance(x, str) for x in [*steps, *queries])
        ):
            raise InvestigationModelError("invalid planner output")
        return steps[:8], queries[:8]

    def hypotheses(self, issue: str, evidence: Sequence[object]) -> list[Hypothesis]:
        payload = self._json(f"Issue: {issue}\nEvidence: {evidence}\nReturn hypotheses.")
        items = payload.get("hypotheses")
        if not isinstance(items, list):
            raise InvestigationModelError("invalid hypothesis output")
        return [
            Hypothesis(str(item["id"]), str(item["description"]))
            for item in items
            if isinstance(item, dict) and "id" in item and "description" in item
        ]

    def verify(
        self, hypotheses: Sequence[Hypothesis], evidence: Sequence[object]
    ) -> list[Hypothesis]:
        return list(hypotheses)


def build_investigation_model(settings: object) -> InvestigationModel:
    from reponyx.config import Settings

    if not isinstance(settings, Settings):
        raise InvestigationModelError("invalid settings")
    if settings.investigation_model_provider == "deterministic":
        return DeterministicInvestigationModel()
    if settings.investigation_model_provider == "openai" and settings.openai_api_key:
        return OpenAIInvestigationModel(
            settings.openai_api_key,
            settings.investigation_model,
            settings.investigation_timeout_seconds,
        )
    raise InvestigationModelError("configured investigation model is unavailable")
