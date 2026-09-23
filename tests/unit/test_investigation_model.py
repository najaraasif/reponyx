from reponyx.investigation.model import ClassifiedEvidence, DeterministicInvestigationModel
from reponyx.investigation.models import Confidence, Evidence, VerificationStatus


def test_deterministic_model_separates_plan_and_hypothesis() -> None:
    model = DeterministicInvestigationModel()
    steps, queries = model.plan("Users cannot reset their password", {})
    hypotheses = model.hypotheses("Users cannot reset their password", [])

    assert steps
    assert queries
    assert hypotheses[0].verification_status.value == "unverified"


def test_plan_always_produces_queries_for_non_auth_issues() -> None:
    model = DeterministicInvestigationModel()
    _, queries = model.plan(
        "Population variance returns wrong value. Expected 2.0 for [1,2,3,4,5], reported 2.5.",
        {},
    )
    assert len(queries) >= 2, "plan must produce queries for non-authentication issues"
    assert "related tests" in queries


def test_plan_extracts_keywords_from_issue() -> None:
    model = DeterministicInvestigationModel()
    _, queries = model.plan("median calculation fails on even-length lists", {})
    assert any("median" in q for q in queries), "queries should contain issue keyword 'median'"


def test_hypotheses_with_evidence() -> None:
    model = DeterministicInvestigationModel()
    ev = Evidence(
        evidence_id="chunk-1",
        type="retrieval_result",
        file_path="src/statistics.py",
        symbol="variance",
        start_line=10,
        end_line=20,
        description="Variance function",
        source_reference="src/statistics.py:10-20",
    )
    hypotheses = model.hypotheses("variance bug", [ev])
    assert len(hypotheses) == 1
    assert hypotheses[0].supporting_evidence == ["chunk-1"]


def test_rca_contains_specific_evidence_backed_findings() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            evidence_id="ev-1",
            type="retrieval_result",
            file_path="src/statistics.py",
            symbol="variance",
            start_line=30,
            end_line=33,
            description="Variance function",
            source_reference="src/statistics.py:30-33",
        ),
        Evidence(
            evidence_id="ev-2",
            type="source_code",
            file_path="src/statistics.py",
            symbol=None,
            start_line=30,
            end_line=33,
            description="Source inspection",
            source_reference="src/statistics.py:30-33",
        ),
        Evidence(
            evidence_id="ev-3",
            type="retrieval_result",
            file_path="tests/test_statistics.py",
            symbol="test_variance",
            start_line=35,
            end_line=40,
            description="Test function",
            source_reference="tests/test_statistics.py:35-40",
        ),
    ]
    hypotheses = model.hypotheses(
        "Population variance returns wrong value. Expected 2.0, reported 2.5.",
        evidence,
    )
    desc = hypotheses[0].description
    assert "src/statistics.py" in desc, "RCA must cite affected source file"
    assert "tests/test_statistics.py" in desc, "RCA must cite test file"
    assert "variance" in desc, "RCA must mention relevant symbol"
    assert "ev-1" in desc or "ev-2" in desc or "ev-3" in desc, "RCA must reference evidence IDs"
    assert len(desc) > 100, "RCA must be detailed, not generic"


def test_rca_cites_evidence_ids() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            evidence_id="chunk-abc-123",
            type="retrieval_result",
            file_path="src/auth.py",
            symbol="login",
            start_line=1,
            end_line=10,
            description="Login function",
            source_reference="src/auth.py:1-10",
        ),
    ]
    hypotheses = model.hypotheses("login fails", evidence)
    assert "chunk-abc-123" in hypotheses[0].description


def test_variance_case_does_not_propose_unnecessary_patch() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            evidence_id="ev-var",
            type="retrieval_result",
            file_path="src/statistics.py",
            symbol="variance",
            start_line=30,
            end_line=33,
            description="def variance(values): return float(np.var(array))",
            source_reference="src/statistics.py:30-33",
        ),
        Evidence(
            evidence_id="ev-test",
            type="retrieval_result",
            file_path="tests/test_statistics.py",
            symbol="test_variance",
            start_line=35,
            end_line=45,
            description="test for variance",
            source_reference="tests/test_statistics.py:35-45",
        ),
        Evidence(
            evidence_id="ev-src",
            type="source_code",
            file_path="src/statistics.py",
            symbol=None,
            start_line=30,
            end_line=33,
            description="source inspection",
            source_reference="src/statistics.py:30-33",
        ),
    ]
    hypotheses = model.hypotheses(
        "Population variance returns wrong value. Expected 2.0 for [1,2,3,4,5], reported 2.5.",
        evidence,
    )
    desc = hypotheses[0].description.lower()
    assert "np.var" in desc or "variance" in desc, "RCA should reference the implementation details"
    verified = model.verify(hypotheses, evidence)
    assert verified[0].verification_status == VerificationStatus.SUPPORTED
    assert verified[0].supporting_evidence


def test_generic_fallback_when_evidence_insufficient() -> None:
    model = DeterministicInvestigationModel()
    hypotheses = model.hypotheses("completely unknown issue with no evidence", [])
    desc = hypotheses[0].description
    assert "insufficient" in desc.lower()
    assert hypotheses[0].verification_status == VerificationStatus.UNVERIFIED
    verified = model.verify(hypotheses, [])
    assert verified[0].verification_status == VerificationStatus.INCONCLUSIVE
    assert verified[0].confidence == Confidence.LOW


def test_verify_confidence_scales_with_evidence_count() -> None:
    model = DeterministicInvestigationModel()
    few_evidence = [
        Evidence(
            f"e{i}", "retrieval_result", f"src/file{i}.py", f"sym{i}", 1, 10, "desc", f"ref{i}"
        )
        for i in range(3)
    ]
    many_evidence = [
        Evidence(
            f"e{i}", "retrieval_result", f"src/file{i}.py", f"sym{i}", 1, 10, "desc", f"ref{i}"
        )
        for i in range(5)
    ] + [
        Evidence(f"src-e{i}", "source_code", f"src/file{i}.py", None, 1, 10, "src", f"ref{i}")
        for i in range(8)
    ]
    few_hyp = model.hypotheses("test issue", few_evidence)
    many_hyp = model.hypotheses("test issue", many_evidence)
    few_verified = model.verify(few_hyp, few_evidence)
    many_verified = model.verify(many_hyp, many_evidence)
    assert few_verified[0].confidence == Confidence.LOW
    assert many_verified[0].confidence == Confidence.HIGH


def test_verify_requires_source_code_for_medium_confidence() -> None:
    model = DeterministicInvestigationModel()
    retrieval_only = [
        Evidence(
            f"e{i}", "retrieval_result", f"src/file{i}.py", f"sym{i}", 1, 10, "desc", f"ref{i}"
        )
        for i in range(5)
    ]
    hyp = model.hypotheses("test", retrieval_only)
    verified = model.verify(hyp, retrieval_only)
    assert verified[0].confidence == Confidence.LOW, (
        "Without source_code evidence, confidence should remain LOW"
    )


def test_variance_rca_identifies_impl_and_tests() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-stat",
            "source_code",
            "src/statistics.py",
            None,
            30,
            33,
            "source inspection",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-var",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "Variance function",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-test",
            "retrieval_result",
            "tests/test_statistics.py",
            "test_variance",
            35,
            45,
            "test for variance",
            "tests/test_statistics.py:35-45",
        ),
    ]
    hyp = model.hypotheses(
        "Population variance returns wrong value. Expected 2.0 for [1,2,3,4,5], reported 2.5.",
        evidence,
    )
    desc = hyp[0].description
    assert "src/statistics.py" in desc
    assert "tests/test_statistics.py" in desc
    assert "variance" in desc


def test_variance_rca_identifies_expected_actual_values() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-var",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "Variance function",
            "src/statistics.py:30-33",
        ),
    ]
    hyp = model.hypotheses(
        "Population variance returns wrong value. "
        "Expected 2.0 for [1,2,3,4,5], reported actual 2.5.",
        evidence,
    )
    desc = hyp[0].description
    assert "expected" in desc.lower()
    assert "2.0" in desc or "actual" in desc.lower()


def test_unrelated_simulation_not_primary_rca() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-stat",
            "source_code",
            "src/statistics.py",
            "variance",
            30,
            33,
            "source",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-sim",
            "retrieval_result",
            "src/simulation.py",
            "estimate_pi",
            4,
            19,
            "pi estimation",
            "src/simulation.py:4-19",
        ),
    ]
    hyp = model.hypotheses(
        "Population variance returns wrong value. Expected 2.0, reported 2.5.",
        evidence,
    )
    desc = hyp[0].description.lower()
    assert "src/statistics.py" in desc
    assert "variance" in desc


def test_insufficient_evidence_produces_unknown() -> None:
    model = DeterministicInvestigationModel()
    hyp = model.hypotheses("unknown issue with no evidence", [])
    desc = hyp[0].description.lower()
    assert "insufficient" in desc
    assert hyp[0].verification_status == VerificationStatus.UNVERIFIED


def test_rca_contains_evidence_ids_and_source_locations() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-abc-123",
            "retrieval_result",
            "src/auth.py",
            "login",
            1,
            10,
            "Login function",
            "src/auth.py:1-10",
        ),
        Evidence(
            "source-src/auth.py-1",
            "source_code",
            "src/auth.py",
            None,
            1,
            10,
            "source inspection",
            "src/auth.py:1-10",
        ),
    ]
    hyp = model.hypotheses("login fails", evidence)
    desc = hyp[0].description
    assert "ev-abc-123" in desc
    assert "src/auth.py:1-10" in desc


def test_noisy_file_terms_filtered() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "desc",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2",
            "retrieval_result",
            "benchmark_statistics.py",
            "python_mean",
            1,
            5,
            "desc",
            "benchmark_statistics.py:1-5",
        ),
    ]
    hyp = model.hypotheses(
        "Population variance returns wrong value. Expected 2.0, reported 2.5.",
        evidence,
    )
    desc = hyp[0].description
    assert "src/statistics.py" in desc
    assert "variance" in desc.lower()


def test_classify_evidence_primary_implementation() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "desc",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2",
            "retrieval_result",
            "src/simulation.py",
            "estimate_pi",
            4,
            19,
            "desc",
            "src/simulation.py:4-19",
        ),
    ]
    classified = model._classify_evidence(evidence, ["variance"])
    assert "src/statistics.py" in classified.primary_implementation_files
    assert "src/simulation.py" not in classified.primary_implementation_files
    assert "variance" in classified.primary_implementation_symbols


def test_classify_evidence_primary_test() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "tests/test_statistics.py",
            "test_variance",
            35,
            45,
            "desc",
            "tests/test_statistics.py:35-45",
        ),
        Evidence(
            "ev-2",
            "retrieval_result",
            "tests/test_simulation.py",
            "test_pi",
            10,
            20,
            "desc",
            "tests/test_simulation.py:10-20",
        ),
    ]
    classified = model._classify_evidence(evidence, ["variance"])
    assert "tests/test_statistics.py" in classified.primary_test_files
    assert "tests/test_simulation.py" not in classified.primary_test_files
    assert "test_variance" in classified.primary_test_symbols


def test_classify_evidence_supporting_vs_unrelated() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "desc",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2",
            "retrieval_result",
            "tests/test_statistics.py",
            "test_variance",
            35,
            45,
            "desc",
            "tests/test_statistics.py:35-45",
        ),
        Evidence(
            "ev-3",
            "retrieval_result",
            "src/simulation.py",
            "estimate_pi",
            4,
            19,
            "desc",
            "src/simulation.py:4-19",
        ),
        Evidence(
            "ev-4",
            "retrieval_result",
            "tests/test_simulation.py",
            "test_pi",
            10,
            20,
            "desc",
            "tests/test_simulation.py:10-20",
        ),
    ]
    classified = model._classify_evidence(evidence, ["variance"])
    assert "ev-1" in classified.supporting_evidence_ids
    assert "ev-2" in classified.supporting_evidence_ids
    assert "ev-3" in classified.unrelated_evidence_ids
    assert "ev-4" in classified.unrelated_evidence_ids


def test_variance_rca_n_vs_n_minus_1() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "def variance(values): return float(np.var(array))",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2",
            "source_code",
            "src/statistics.py",
            None,
            30,
            33,
            "source inspection",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-3",
            "retrieval_result",
            "tests/test_statistics.py",
            "test_variance",
            35,
            45,
            "test for variance",
            "tests/test_statistics.py:35-45",
        ),
    ]
    issue = (
        "Population variance returns wrong value. "
        "Expected 2.0 for [1,2,3,4,5], reported actual 2.5."
    )
    hyp = model.hypotheses(issue, evidence)
    desc = hyp[0].description.lower()
    assert "population variance" in desc
    assert "sample variance" in desc
    assert "divides by n" in desc or "len(values) - 1" in desc
    assert "2.0" in desc and "2.5" in desc


def test_variance_expected_actual_extraction() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "desc",
            "src/statistics.py:30-33",
        ),
    ]
    issue = (
        "Population variance returns wrong value. "
        "Expected 2.0 for [1,2,3,4,5], reported actual 2.5."
    )
    hyp = model.hypotheses(issue, evidence)
    desc = hyp[0].description
    assert "expected" in desc.lower()
    assert "2.0" in desc
    assert "actual" in desc.lower()
    assert "2.5" in desc


def test_evidence_ids_and_line_ranges_in_rca() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-abc-123",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "desc",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "source-src/statistics.py-30",
            "source_code",
            "src/statistics.py",
            None,
            30,
            33,
            "source inspection",
            "src/statistics.py:30-33",
        ),
    ]
    hyp = model.hypotheses(
        "Population variance returns wrong value. Expected 2.0, reported 2.5.",
        evidence,
    )
    desc = hyp[0].description
    assert "ev-abc-123" in desc
    assert "src/statistics.py:30-33" in desc


def test_insufficient_evidence_fallback() -> None:
    model = DeterministicInvestigationModel()
    hyp = model.hypotheses("unknown issue with no evidence", [])
    desc = hyp[0].description.lower()
    assert "insufficient" in desc
    assert hyp[0].verification_status == VerificationStatus.UNVERIFIED
    verified = model.verify(hyp, [])
    assert verified[0].verification_status == VerificationStatus.INCONCLUSIVE
    assert verified[0].confidence == Confidence.LOW


def test_classification_structured_output() -> None:
    model = DeterministicInvestigationModel()
    evidence = [
        Evidence(
            "ev-1",
            "retrieval_result",
            "src/statistics.py",
            "variance",
            30,
            33,
            "desc",
            "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2",
            "retrieval_result",
            "tests/test_statistics.py",
            "test_variance",
            35,
            45,
            "desc",
            "tests/test_statistics.py:35-45",
        ),
    ]
    classified = model._classify_evidence(evidence, ["variance"])
    assert isinstance(classified, ClassifiedEvidence)
    assert len(classified.primary_implementation_files) == 1
    assert len(classified.primary_test_files) == 1
    assert len(classified.supporting_evidence_ids) == 2
    assert len(classified.evidence_ids) == 2
    assert len(classified.source_locations) == 2


def test_defect_explanation_with_variance() -> None:
    model = DeterministicInvestigationModel()
    classified = ClassifiedEvidence(
        primary_implementation_files=("src/statistics.py",),
        primary_implementation_symbols=("variance",),
    )
    issue = (
        "Population variance returns wrong value. "
        "Expected 2.0 for [1,2,3,4,5], reported actual 2.5."
    )
    explanation = model._explain_defect(issue, classified, [])
    assert "population variance" in explanation.lower()
    assert "sample variance" in explanation.lower()
    assert "2.0" in explanation
    assert "2.5" in explanation
    assert "divides by" in explanation.lower()


def test_ranker_classifies_variance_evidence() -> None:
    from reponyx.investigation.ranker import classify_evidence
    from reponyx.investigation.models import EvidenceCategory

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/statistics.py", "variance",
            30, 33, "Variance function", "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2", "retrieval_result", "tests/test_statistics.py", "test_variance",
            35, 45, "Test variance", "tests/test_statistics.py:35-45",
        ),
        Evidence(
            "ev-3", "retrieval_result", "src/simulation.py", "estimate_pi",
            4, 19, "Pi estimation", "src/simulation.py:4-19",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value. Expected 2.0, reported 2.5.",
    )
    impl = [c for c in classified if c.category == EvidenceCategory.PRIMARY_IMPLEMENTATION]
    tests = [c for c in classified if c.category == EvidenceCategory.PRIMARY_TESTS]
    unrelated = [c for c in classified if c.category == EvidenceCategory.UNRELATED]

    assert len(impl) == 1
    assert impl[0].file_path == "src/statistics.py"
    assert len(tests) == 1
    assert tests[0].file_path == "tests/test_statistics.py"
    assert len(unrelated) == 1
    assert unrelated[0].file_path == "src/simulation.py"


def test_ranker_direct_references_for_source_inspection() -> None:
    from reponyx.investigation.ranker import classify_evidence
    from reponyx.investigation.models import EvidenceCategory

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/statistics.py", "variance",
            30, 33, "Variance function", "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2", "retrieval_result", "src/api.py", "compute_stats",
            10, 15, "Calls variance", "src/api.py:10-15",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value.",
    )
    impl = [c for c in classified if c.category == EvidenceCategory.PRIMARY_IMPLEMENTATION]
    assert len(impl) == 1
    assert impl[0].file_path == "src/statistics.py"


def test_ranker_source_code_with_symbol_is_direct_reference() -> None:
    from reponyx.investigation.ranker import classify_evidence
    from reponyx.investigation.models import EvidenceCategory

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/statistics.py", "variance",
            30, 33, "Variance function", "src/statistics.py:30-33",
        ),
        Evidence(
            "source-src/api.py-10", "source_code", "src/api.py", "compute_stats",
            10, 15, "Source inspection of compute_stats", "src/api.py:10-15",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value.",
    )
    direct = [c for c in classified if c.category == EvidenceCategory.DIRECT_REFERENCES]
    assert len(direct) == 1
    assert direct[0].evidence_id == "source-src/api.py-10"


def test_ranker_unrelated_evidence() -> None:
    from reponyx.investigation.ranker import classify_evidence
    from reponyx.investigation.models import EvidenceCategory

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/simulation.py", "estimate_pi",
            4, 19, "Pi estimation", "src/simulation.py:4-19",
        ),
        Evidence(
            "ev-2", "retrieval_result", "tests/test_simulation.py", "test_pi",
            10, 20, "Test pi", "tests/test_simulation.py:10-20",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value.",
    )
    unrelated = [c for c in classified if c.category == EvidenceCategory.UNRELATED]
    assert len(unrelated) == 2


def test_ranker_empty_evidence() -> None:
    from reponyx.investigation.ranker import classify_evidence

    classified = classify_evidence([], "any issue")
    assert classified == []


def test_ranker_no_matching_symbols() -> None:
    from reponyx.investigation.ranker import classify_evidence
    from reponyx.investigation.models import EvidenceCategory

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/utils.py", "helper",
            1, 10, "Helper function", "src/utils.py:1-10",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value.",
    )
    assert len(classified) == 1
    assert classified[0].category == EvidenceCategory.UNRELATED


def test_ranker_multi_file_relevance() -> None:
    from reponyx.investigation.ranker import classify_evidence
    from reponyx.investigation.models import EvidenceCategory

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/statistics.py", "variance",
            30, 33, "Variance function", "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2", "retrieval_result", "src/statistics.py", "mean",
            10, 15, "Mean function", "src/statistics.py:10-15",
        ),
        Evidence(
            "ev-3", "retrieval_result", "tests/test_statistics.py", "test_variance",
            35, 45, "Test variance", "tests/test_statistics.py:35-45",
        ),
        Evidence(
            "ev-4", "retrieval_result", "tests/test_statistics.py", "test_mean",
            50, 60, "Test mean", "tests/test_statistics.py:50-60",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value.",
    )
    impl = [c for c in classified if c.category == EvidenceCategory.PRIMARY_IMPLEMENTATION]
    tests = [c for c in classified if c.category == EvidenceCategory.PRIMARY_TESTS]
    assert len(impl) == 1
    assert impl[0].symbol == "variance"
    assert len(tests) == 1
    assert tests[0].symbol == "test_variance"


def test_ranker_relevance_score_ordering() -> None:
    from reponyx.investigation.ranker import classify_evidence

    evidence = [
        Evidence(
            "ev-1", "retrieval_result", "src/statistics.py", "variance",
            30, 33, "Variance function", "src/statistics.py:30-33",
        ),
        Evidence(
            "ev-2", "retrieval_result", "src/statistics.py", "helper",
            1, 10, "Helper function", "src/statistics.py:1-10",
        ),
    ]
    classified = classify_evidence(
        evidence,
        "Population variance returns wrong value.",
    )
    assert len(classified) == 2
    assert classified[0].relevance_score >= classified[1].relevance_score
