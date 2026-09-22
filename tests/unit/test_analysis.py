from pathlib import Path

from reponyx.repositories.analyzer import analyze_repository
from reponyx.repositories.languages import extract_tree_entities

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mixed_repo"


def test_python_symbols_and_imports_are_extracted() -> None:
    symbols, imports = extract_tree_entities(
        "repo", "auth.py", "python", (FIXTURE / "app" / "auth.py").read_bytes()
    )

    assert {symbol.name for symbol in symbols} >= {"requires_auth", "AuthService", "reset_password"}
    assert any(symbol.symbol_type.value == "method" for symbol in symbols)
    assert symbols[0].start_line >= 1


def test_typescript_interfaces_classes_and_imports_are_extracted() -> None:
    symbols, imports = extract_tree_entities(
        "repo", "routes.ts", "typescript", (FIXTURE / "app" / "routes.ts").read_bytes()
    )

    assert {symbol.name for symbol in symbols} >= {"ResetRequest", "PasswordController", "reset"}
    assert any(reference.is_export for reference in imports)
    assert any("AuthService" in reference.target for reference in imports)


def test_analysis_isolates_malformed_files_and_creates_logical_chunks(tmp_path) -> None:
    target = tmp_path / "repo"
    target.mkdir()
    (target / "valid.py").write_text("def hello():\n    return 'hello'\n")
    (target / "malformed.py").write_text("def broken(:\n")

    analysis = analyze_repository("repo", target, 1_000, 20, 10_000)

    assert "valid.py" in analysis.files
    assert analysis.chunks[0].symbol == "hello"
    assert "malformed.py" in analysis.files
    assert "malformed.py" in analysis.parse_failures


def test_mixed_repository_map_contains_languages_packages_and_tests() -> None:
    analysis = analyze_repository("repo", FIXTURE, 1_000_000, 100, 10_000_000)

    assert analysis.languages["python"] >= 2
    assert analysis.languages["typescript"] == 1
    assert "Python" in analysis.package_managers
    assert "Node.js" in analysis.package_managers
    assert any(path.startswith("tests/") for path in analysis.test_locations)
    assert any(symbol.name == "PasswordController" for symbol in analysis.symbols)
