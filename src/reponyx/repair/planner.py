"""Cross-file repair planner that identifies all files affected by a defect."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AffectedFile:
    """A file that needs changes as part of a multi-file repair."""

    file_path: str
    reason: str
    confidence: float  # 0.0 to 1.0


class CrossFilePlanner:
    """Analyzes a workspace to identify all files affected by a defect.

    Given a primary file (where the root cause lives), the planner finds:
    - Files that import symbols from the primary file
    - Test files that test the primary file's functionality
    - Configuration files that reference the primary file
    """

    def plan(
        self,
        workspace: Path,
        primary_file: str,
        issue: str,
        evidence: list[object] | None = None,
    ) -> list[AffectedFile]:
        """Identify all files that need changes given a primary defect file.

        Args:
            workspace: Path to the repository workspace.
            primary_file: The file where the root cause lives (e.g. "src/api.py").
            issue: The issue description.
            evidence: Optional investigation evidence.

        Returns:
            List of affected files with reasons and confidence scores.
        """
        if not primary_file:
            return []

        affected: dict[str, AffectedFile] = {}

        # Always include the primary file
        affected[primary_file] = AffectedFile(
            file_path=primary_file,
            reason="primary defect location",
            confidence=1.0,
        )

        # Find importers of the primary file
        importers = self._find_importers(workspace, primary_file)
        for imp in importers:
            if imp.file_path not in affected:
                affected[imp.file_path] = imp

        # Find test files for the primary file
        test_files = self._find_test_files(workspace, primary_file)
        for tf in test_files:
            if tf.file_path not in affected:
                affected[tf.file_path] = tf

        # Find files that reference symbols defined in the primary file
        symbol_refs = self._find_symbol_references(workspace, primary_file)
        for sr in symbol_refs:
            if sr.file_path not in affected:
                affected[sr.file_path] = sr

        return sorted(affected.values(), key=lambda a: (-a.confidence, a.file_path))

    def _find_importers(self, workspace: Path, target_file: str) -> list[AffectedFile]:
        """Find files that import from the target file."""
        target_module = self._file_to_module(target_file)
        if not target_module:
            return []

        results: list[AffectedFile] = []
        for py_file in workspace.rglob("*.py"):
            rel = py_file.relative_to(workspace).as_posix()
            if rel == target_file:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                imported = False
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if self._matches_module(alias.name, target_module):
                            imported = True
                elif isinstance(node, ast.ImportFrom):
                    if node.module and self._matches_module(node.module, target_module):
                        imported = True

                if imported:
                    results.append(
                        AffectedFile(
                            file_path=rel,
                            reason=f"imports from {target_file}",
                            confidence=0.8,
                        )
                    )
                    break  # One match per file is enough

        return results

    def _find_test_files(self, workspace: Path, source_file: str) -> list[AffectedFile]:
        """Find test files that test the given source file."""
        source_name = Path(source_file).stem
        results: list[AffectedFile] = []

        # Common test naming patterns
        test_patterns = [
            f"test_{source_name}.py",
            f"{source_name}_test.py",
            f"tests/test_{source_name}.py",
            f"tests/{source_name}_test.py",
            f"test/test_{source_name}.py",
        ]

        for pattern in test_patterns:
            test_path = workspace / pattern
            if test_path.is_file():
                rel = test_path.relative_to(workspace).as_posix()
                results.append(
                    AffectedFile(
                        file_path=rel,
                        reason=f"tests {source_file}",
                        confidence=0.9,
                    )
                )

        # Also search for test files that import the source module
        source_module = self._file_to_module(source_file)
        if source_module:
            for py_file in workspace.rglob("test_*.py"):
                rel = py_file.relative_to(workspace).as_posix()
                if any(r.file_path == rel for r in results):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and self._matches_module(node.module, source_module):
                            results.append(
                                AffectedFile(
                                    file_path=rel,
                                    reason=f"imports from {source_file}",
                                    confidence=0.85,
                                )
                            )
                            break

        return results

    def _find_symbol_references(self, workspace: Path, source_file: str) -> list[AffectedFile]:
        """Find files that reference symbols defined in the source file."""
        if not source_file:
            return []

        defined_symbols = self._extract_defined_symbols(workspace / source_file)
        if not defined_symbols:
            return []

        results: list[AffectedFile] = []
        for py_file in workspace.rglob("*.py"):
            rel = py_file.relative_to(workspace).as_posix()
            if rel == source_file:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            referenced = set()
            for symbol in defined_symbols:
                # Simple heuristic: check if symbol name appears in the file
                # This is a lightweight check; full AST analysis would be slower
                if re.search(rf"\b{re.escape(symbol)}\b", source):
                    referenced.add(symbol)

            if referenced:
                results.append(
                    AffectedFile(
                        file_path=rel,
                        reason=f"references symbols: {', '.join(sorted(referenced))}",
                        confidence=0.6,
                    )
                )

        return results

    def _extract_defined_symbols(self, file_path: Path) -> set[str]:
        """Extract top-level function and class names from a Python file."""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            return set()

        symbols: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.add(node.name)
            elif isinstance(node, ast.ClassDef):
                symbols.add(node.name)
                # Also include methods
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.add(item.name)

        return symbols

    @staticmethod
    def _file_to_module(file_path: str) -> str | None:
        """Convert a file path to a Python module path."""
        path = Path(file_path)
        if path.suffix != ".py":
            return None
        parts = list(path.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else None

    @staticmethod
    def _matches_module(import_path: str, target_module: str) -> bool:
        """Check if an import path matches the target module."""
        return import_path == target_module or import_path.startswith(target_module + ".")
