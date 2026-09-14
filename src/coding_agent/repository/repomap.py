"""Deterministic, non-executing Python repository symbol map."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from coding_agent.repository.symbols import RepoMapDiagnostic, RepoSymbol

_EXCLUDED_PARTS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}


class PythonRepoMap:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._by_path: dict[str, tuple[RepoSymbol, ...]] = {}
        self._diagnostics: dict[str, RepoMapDiagnostic] = {}
        self._invalidated: set[str] = set()

    @property
    def symbols(self) -> tuple[RepoSymbol, ...]:
        values = (symbol for items in self._by_path.values() for symbol in items)
        return tuple(sorted(values, key=lambda symbol: symbol.sort_key))

    @property
    def diagnostics(self) -> tuple[RepoMapDiagnostic, ...]:
        return tuple(self._diagnostics[path] for path in sorted(self._diagnostics))

    def build(self) -> None:
        self._by_path.clear()
        self._diagnostics.clear()
        for path in sorted(self.root.rglob("*.py")):
            if not any(part in _EXCLUDED_PARTS for part in path.relative_to(self.root).parts):
                self._parse(path)

    def invalidate(self, path: Path) -> None:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("path is outside repository")
        self._invalidated.add(resolved.relative_to(self.root).as_posix())

    def refresh(self) -> None:
        for relative in sorted(self._invalidated):
            self._by_path.pop(relative, None)
            self._diagnostics.pop(relative, None)
            path = self.root / relative
            if path.is_file() and path.suffix == ".py":
                self._parse(path)
        self._invalidated.clear()

    def select(
        self, query: str, *, paths: tuple[str, ...] = (), limit: int = 30
    ) -> tuple[RepoSymbol, ...]:
        terms = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query.casefold()))
        normalized_paths = {Path(path).as_posix().casefold() for path in paths}

        def score(symbol: RepoSymbol) -> tuple[int, tuple[str, int, str, str]]:
            haystack = f"{symbol.path} {symbol.kind} {symbol.qualified_name}".casefold()
            overlap = sum(1 for term in terms if term in haystack)
            path_match = int(symbol.path.casefold() in normalized_paths)
            return (-(overlap * 10 + path_match * 20), symbol.sort_key)

        return tuple(sorted(self.symbols, key=score)[: max(0, limit)])

    def render(self, symbols: tuple[RepoSymbol, ...], *, max_chars: int) -> str:
        if max_chars <= 0:
            return ""
        lines: list[str] = []
        used = 0
        for symbol in symbols:
            line = symbol.render()
            addition = len(line) + (1 if lines else 0)
            if used + addition > max_chars:
                break
            lines.append(line)
            used += addition
        return "\n".join(lines)

    def _parse(self, path: Path) -> None:
        relative = path.relative_to(self.root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as error:
            self._diagnostics[relative] = RepoMapDiagnostic(relative, str(error))
            self._by_path[relative] = ()
            return
        visitor = _SymbolVisitor(relative)
        visitor.visit(tree)
        self._by_path[relative] = tuple(sorted(visitor.symbols, key=lambda s: s.sort_key))


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.parents: list[str] = []
        self.symbols: list[RepoSymbol] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.symbols.append(RepoSymbol(self.path, "import", alias.name, line=node.lineno))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            self.symbols.append(
                RepoSymbol(self.path, "import", f"{module}.{alias.name}", line=node.lineno)
            )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent = ".".join(self.parents) or None
        self.symbols.append(
            RepoSymbol(self.path, "class", node.name, parent=parent, line=node.lineno)
        )
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parent = ".".join(self.parents) or None
        kind = "method" if parent else "function"
        arguments = list(node.args.args)
        if kind == "method" and arguments and arguments[0].arg in {"self", "cls"}:
            arguments = arguments[1:]
        copied = ast.arguments(
            posonlyargs=node.args.posonlyargs,
            args=arguments,
            vararg=node.args.vararg,
            kwonlyargs=node.args.kwonlyargs,
            kw_defaults=node.args.kw_defaults,
            kwarg=node.args.kwarg,
            defaults=node.args.defaults,
        )
        signature = f"({ast.unparse(copied)})"
        if node.returns is not None:
            signature += f" -> {ast.unparse(node.returns)}"
        self.symbols.append(RepoSymbol(self.path, kind, node.name, signature, parent, node.lineno))
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()
