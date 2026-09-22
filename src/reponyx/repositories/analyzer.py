"""Repository-wide static analysis without executing repository code."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from reponyx.repositories.discovery import discover_files
from reponyx.repositories.languages import ADAPTERS, extract_tree_entities
from reponyx.repositories.models import CodeChunk, Dependency, RepositoryAnalysis, Symbol
from reponyx.repositories.policy import language_for_path

logger = logging.getLogger(__name__)


_PACKAGE_MARKERS = {
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "package.json": "Node.js",
    "pom.xml": "Maven",
    "build.gradle": "Gradle",
    "go.mod": "Go modules",
    "Cargo.toml": "Cargo",
}
_FRAMEWORK_MARKERS = {
    "manage.py": "Django",
    "next.config.js": "Next.js",
    "vite.config.ts": "Vite",
    "angular.json": "Angular",
    "spring": "Spring",
}
_ENTRY_POINTS = {
    "main.py",
    "__main__.py",
    "main.go",
    "Main.java",
    "main.rs",
    "index.js",
    "index.ts",
}
_METADATA_FILES = set(_PACKAGE_MARKERS) | {
    "pytest.ini",
    "tox.ini",
    "jest.config.js",
    "vitest.config.ts",
    "tsconfig.json",
    "angular.json",
}


def _dependency_target(import_text: str, source_file: str, language: str) -> str:
    text = import_text.strip()
    if language == "python":
        return text.split("import", 1)[-1].split("from", 1)[-1].strip().split()[0]
    if language in {"javascript", "typescript"} and "from" in text:
        return text.rsplit("from", 1)[-1].strip().strip("'\";")
    if language == "go":
        return text.strip('import ()"')
    if language == "rust":
        return text.removeprefix("use ").strip(" ;").split("::")[0]
    return text


def _chunks_for_file(
    root: Path, path: str, symbols: list[Symbol], imports: list[str], language: str
) -> list[CodeChunk]:
    content = (root / path).read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    file_symbols = [symbol for symbol in symbols if symbol.file_path == path]
    chunks: list[CodeChunk] = []
    for symbol in file_symbols:
        body = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        chunks.append(
            CodeChunk(
                path,
                symbol.name,
                language,
                symbol.start_line,
                symbol.end_line,
                body,
                symbol.parent_symbol,
                tuple(imports),
            )
        )
    if not chunks and lines:
        chunks.append(CodeChunk(path, None, language, 1, len(lines), content, None, tuple(imports)))
    return chunks


def analyze_repository(
    repository_id: str, root: Path, max_file_bytes: int, max_files: int, max_repository_bytes: int
) -> RepositoryAnalysis:
    analysis = RepositoryAnalysis(repository_id=repository_id, analyzed_at=datetime.now(UTC))
    analysis.files = discover_files(root, max_file_bytes, max_files, max_repository_bytes)
    analysis.configuration_files = sorted(
        candidate.relative_to(root).as_posix()
        for candidate in root.rglob("*")
        if candidate.is_file() and not candidate.is_symlink() and candidate.name in _METADATA_FILES
    )
    analysis.package_managers = sorted(
        {
            _PACKAGE_MARKERS[Path(path).name]
            for path in analysis.configuration_files
            if Path(path).name in _PACKAGE_MARKERS
        }
    )
    analysis.test_locations.extend(
        candidate.relative_to(root).as_posix()
        for candidate in root.rglob("*")
        if candidate.is_dir() and candidate.name.lower() in {"test", "tests", "spec", "specs"}
    )
    analysis.directories = sorted(
        {str(Path(path).parent).replace(".", "") or "." for path in analysis.files}
    )
    all_imports_by_file: dict[str, list[str]] = {}

    for relative in analysis.files:
        path = root / relative
        language = language_for_path(relative)
        if language is None or language not in ADAPTERS:
            continue
        analysis.languages[language] = analysis.languages.get(language, 0) + 1
        filename = Path(relative).name
        if filename in _PACKAGE_MARKERS:
            analysis.package_managers.append(_PACKAGE_MARKERS[filename])
        if filename in _ENTRY_POINTS:
            analysis.entry_points.append(relative)
        if filename in {"pytest.ini", "tox.ini", "jest.config.js", "vitest.config.ts"} or any(
            part.lower() in {"test", "tests", "spec", "specs"} for part in Path(relative).parts
        ):
            analysis.test_locations.append(relative)
        try:
            source = path.read_bytes()
            symbols, imports = extract_tree_entities(repository_id, relative, language, source)
            analysis.symbols.extend(symbols)
            analysis.imports.extend(imports)
            import_texts = [item.target for item in imports if not item.is_export]
            all_imports_by_file[relative] = import_texts
            for item in imports:
                if not item.is_export:
                    analysis.dependencies.append(
                        Dependency(
                            relative, _dependency_target(item.target, relative, language), "import"
                        )
                    )
            analysis.chunks.extend(
                _chunks_for_file(root, relative, symbols, import_texts, language)
            )
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            logger.warning(
                "file_analysis_failed",
                extra={"repository_id": repository_id, "file": relative, "error": str(exc)},
            )
            analysis.parse_failures.append(relative)

    analysis.frameworks = sorted(
        {
            marker
            for path in analysis.files
            for marker in _FRAMEWORK_MARKERS
            if Path(path).name == marker
        }
    )
    analysis.package_managers = sorted(set(analysis.package_managers))
    return analysis
