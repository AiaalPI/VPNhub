#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
}


@dataclass(frozen=True)
class Hit:
    value: str
    file: str
    line: int


def is_callback_query_decorator(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "callback_query"


def is_attr_chain_ending_with_data(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "data"


def const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def literal_strs_from_container(node: ast.AST) -> list[str]:
    values: Iterable[ast.AST]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = node.elts
    else:
        return []

    out: list[str] = []
    for item in values:
        s = const_str(item)
        if s is None:
            return []
        out.append(s)
    return out


class CallbackVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, repo_root: Path) -> None:
        self.file_path = file_path
        self.repo_root = repo_root
        self.used: list[Hit] = []
        self.handled: list[Hit] = []

    def rel_file(self) -> str:
        try:
            return str(self.file_path.relative_to(self.repo_root))
        except ValueError:
            return str(self.file_path)

    def add_used(self, value: str, line: int) -> None:
        self.used.append(Hit(value=value, file=self.rel_file(), line=line))

    def add_handled(self, value: str, line: int) -> None:
        self.handled.append(Hit(value=value, file=self.rel_file(), line=line))

    def visit_Call(self, node: ast.Call) -> None:
        for kw in node.keywords:
            if kw.arg == "callback_data":
                s = const_str(kw.value)
                if s is not None:
                    self.add_used(s, getattr(kw.value, "lineno", node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_callback_decorators(node.decorator_list)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_callback_decorators(node.decorator_list)
        self.generic_visit(node)

    def _visit_callback_decorators(self, decorators: list[ast.expr]) -> None:
        for deco in decorators:
            if not is_callback_query_decorator(deco):
                continue

            for arg in deco.args:
                self._extract_handled_from_expr(arg, deco.lineno)

            for kw in deco.keywords:
                if kw.arg in {"text", "data"}:
                    s = const_str(kw.value)
                    if s is not None:
                        self.add_handled(s, getattr(kw.value, "lineno", deco.lineno))

    def _extract_handled_from_expr(self, node: ast.AST, default_line: int) -> None:
        if isinstance(node, ast.Compare):
            self._extract_from_compare(node, default_line)
            return

        if isinstance(node, ast.Call):
            self._extract_from_call(node, default_line)
            return

        for child in ast.iter_child_nodes(node):
            self._extract_handled_from_expr(child, default_line)

    def _extract_from_compare(self, node: ast.Compare, default_line: int) -> None:
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return
        if not isinstance(node.ops[0], ast.Eq):
            return

        left = node.left
        right = node.comparators[0]
        if is_attr_chain_ending_with_data(left):
            s = const_str(right)
            if s is not None:
                self.add_handled(s, getattr(right, "lineno", default_line))

    def _extract_from_call(self, node: ast.Call, default_line: int) -> None:
        # F.data.in_(["a", "b"]) and similar literal containers.
        if isinstance(node.func, ast.Attribute) and node.func.attr == "in_":
            if is_attr_chain_ending_with_data(node.func.value) and node.args:
                for s in literal_strs_from_container(node.args[0]):
                    self.add_handled(s, getattr(node.args[0], "lineno", default_line))

        for child in ast.iter_child_nodes(node):
            self._extract_handled_from_expr(child, default_line)


def iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix == ".py":
        yield root
        return

    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        yield path


def analyze(root: Path, repo_root: Path) -> tuple[list[Hit], list[Hit], list[str]]:
    used: list[Hit] = []
    handled: list[Hit] = []
    warnings: list[str] = []

    for py_file in iter_python_files(root):
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            warnings.append(f"WARN skip read {py_file}: {exc}")
            continue

        try:
            tree = ast.parse(text, filename=str(py_file))
        except SyntaxError as exc:
            warnings.append(f"WARN skip syntax {py_file}:{exc.lineno}: {exc.msg}")
            continue

        visitor = CallbackVisitor(py_file, repo_root)
        visitor.visit(tree)
        used.extend(visitor.used)
        handled.extend(visitor.handled)

    return used, handled, warnings


def dedupe_hits(hits: list[Hit]) -> dict[str, list[Hit]]:
    grouped: dict[str, list[Hit]] = {}
    seen: set[tuple[str, str, int]] = set()
    for h in hits:
        key = (h.value, h.file, h.line)
        if key in seen:
            continue
        seen.add(key)
        grouped.setdefault(h.value, []).append(h)

    for value in grouped:
        grouped[value].sort(key=lambda x: (x.file, x.line))
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect callback_data literals used in keyboards but not handled in callback_query decorators.")
    parser.add_argument("--root", default="bot/bot", help="Root directory (or file) to scan. Default: bot/bot")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON output")
    args = parser.parse_args()

    repo_root = Path.cwd()
    root = Path(args.root)
    if not root.is_absolute():
        root = (repo_root / root).resolve()

    if not root.exists():
        print(f"ERROR: root path does not exist: {root}", file=sys.stderr)
        return 1

    used_hits, handled_hits, warnings = analyze(root, repo_root)
    used_map = dedupe_hits(used_hits)
    handled_map = dedupe_hits(handled_hits)

    used_set = set(used_map)
    handled_set = set(handled_map)
    missing = sorted(used_set - handled_set)
    unused_handlers = sorted(handled_set - used_set)

    if args.as_json:
        payload = {
            "root": str(root),
            "counts": {
                "used": len(used_set),
                "handled": len(handled_set),
                "missing": len(missing),
                "unused_handlers": len(unused_handlers),
                "warnings": len(warnings),
            },
            "missing": [
                {
                    "callback_data": item,
                    "used_at": [
                        {"file": hit.file, "line": hit.line}
                        for hit in used_map.get(item, [])
                    ],
                }
                for item in missing
            ],
            "unused_handlers": [
                {
                    "callback_data": item,
                    "handled_at": [
                        {"file": hit.file, "line": hit.line}
                        for hit in handled_map.get(item, [])
                    ],
                }
                for item in unused_handlers
            ],
            "warnings": warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Root: {root}")
        print(f"Used callback_data (literals): {len(used_set)}")
        print(f"Handled callback filters (literals): {len(handled_set)}")
        print(f"Missing handlers: {len(missing)}")
        print(f"Potentially unused handlers: {len(unused_handlers)}")

        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"- {w}")

        if missing:
            print("\nMissing callback handlers (used but not handled):")
            for item in missing:
                refs = used_map.get(item, [])
                locations = ", ".join(f"{h.file}:{h.line}" for h in refs)
                print(f"- {item}: {locations}")

        if unused_handlers:
            print("\nPotentially unused handled callbacks (warn only):")
            for item in unused_handlers:
                refs = handled_map.get(item, [])
                locations = ", ".join(f"{h.file}:{h.line}" for h in refs)
                print(f"- {item}: {locations}")

    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
