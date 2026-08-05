#!/usr/bin/env python3
"""Compile every standalone C++ example in the Rust/HFT mdBook.

Fences tagged ``cpp`` are treated as complete, single-file C++20 programs.
Teaching fragments, multi-file examples, platform-specific code, and deliberate
compile errors must use ``cpp,ignore`` and explain the reason in the chapter.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPOSITORY_ROOT / "books" / "rust-hft" / "src"
OPENING_FENCE = re.compile(r"^(?P<indent>[ \t]*)```(?P<info>[^`]*)$")
CLOSING_FENCE = re.compile(r"^[ \t]*```[ \t]*$")
MAIN_FUNCTION = re.compile(r"\b(?:int|auto)\s+main\s*\(")


@dataclass(frozen=True)
class CppExample:
    chapter: Path
    line: int
    code: str


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path)


def cpp_examples(markdown_path: Path) -> tuple[list[CppExample], list[str]]:
    """Return non-ignored C++ blocks and parser errors from one chapter."""
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    examples: list[CppExample] = []
    errors: list[str] = []
    index = 0

    while index < len(lines):
        match = OPENING_FENCE.match(lines[index])
        if not match:
            index += 1
            continue

        info = match.group("info").strip()
        language, *attributes = [part.strip() for part in info.split(",")]
        if language.lower() not in {"cpp", "c++"}:
            index += 1
            continue

        opening_line = index + 1
        index += 1
        body: list[str] = []
        while index < len(lines) and not CLOSING_FENCE.match(lines[index]):
            body.append(lines[index])
            index += 1

        if index == len(lines):
            errors.append(
                f"{display_path(markdown_path)}:{opening_line}: C++ 代码围栏未闭合"
            )
            break

        if "ignore" not in {attribute.lower() for attribute in attributes}:
            code = textwrap.dedent("\n".join(body)).strip() + "\n"
            examples.append(CppExample(markdown_path, opening_line, code))
        index += 1

    return examples, errors


def find_compiler(explicit: str | None) -> str | None:
    candidates = [explicit, os.environ.get("CXX"), "clang++", "g++", "c++"]
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="提取并编译书中未标记 ignore 的独立 C++20 示例。"
    )
    parser.add_argument(
        "source_root",
        nargs="?",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="mdBook src 目录，默认 books/rust-hft/src",
    )
    parser.add_argument("--compiler", help="指定 C++ 编译器，默认依次寻找 CXX、clang++、g++")
    parser.add_argument(
        "--run",
        action="store_true",
        help="编译后运行每个示例；每个程序最多等待 10 秒",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    source_root = arguments.source_root.resolve()
    compiler = find_compiler(arguments.compiler)
    if compiler is None:
        print("ERROR: 未找到 C++ 编译器；请安装 Clang 或 GCC。", file=sys.stderr)
        return 1

    examples: list[CppExample] = []
    errors: list[str] = []
    for chapter in sorted(source_root.rglob("*.md")):
        chapter_examples, chapter_errors = cpp_examples(chapter)
        examples.extend(chapter_examples)
        errors.extend(chapter_errors)

    with tempfile.TemporaryDirectory(prefix="hft-book-cpp-") as temporary:
        temporary_root = Path(temporary)
        for number, example in enumerate(examples, start=1):
            location = f"{display_path(example.chapter)}:{example.line}"
            if not MAIN_FUNCTION.search(example.code):
                errors.append(
                    f"{location}: ```cpp 必须是含 main 的完整程序；片段请使用 ```cpp,ignore"
                )
                continue

            source_file = temporary_root / f"example_{number:03d}.cpp"
            source_file.write_text(example.code, encoding="utf-8")
            executable_file = temporary_root / f"example_{number:03d}"
            command = [
                compiler,
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-pthread",
                str(source_file),
                "-o",
                str(executable_file),
            ]
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            if completed.returncode != 0:
                diagnostic = completed.stderr.strip() or completed.stdout.strip()
                errors.append(f"{location}: 编译失败\n{diagnostic}")
                continue

            if arguments.run:
                try:
                    execution = subprocess.run(
                        [str(executable_file)],
                        text=True,
                        capture_output=True,
                        check=False,
                        timeout=10,
                    )
                except subprocess.TimeoutExpired:
                    errors.append(f"{location}: 运行超过 10 秒，可能阻塞或工作量过大")
                    continue
                if execution.returncode != 0:
                    diagnostic = execution.stderr.strip() or execution.stdout.strip()
                    errors.append(
                        f"{location}: 运行失败，退出码 {execution.returncode}\n{diagnostic}"
                    )

    print(f"C++ compiler: {compiler}")
    print(f"Standalone examples: {len(examples)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"C++ example check failed with {len(errors)} error(s).", file=sys.stderr)
        return 1

    action = "compiled and ran" if arguments.run else "compiled"
    print(f"All standalone C++20 examples {action} successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
