#!/usr/bin/env python3
"""Dependency-free structural checks for one or more mdBook projects."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOK_ROOTS = (
    REPOSITORY_ROOT / "books" / "rust-hft",
    REPOSITORY_ROOT / "books" / "ai",
)

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
DRAFT_MARKER = re.compile(
    r"\b(?:TODO|TBD|FIXME|WIP)\b|待补充|占位内容",
    re.IGNORECASE,
)
FENCE_LINE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")


@dataclass
class BookResult:
    root: Path
    chapters: int = 0
    listed_chapters: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def display_path(path: Path) -> str:
    """Show repository-relative paths where possible."""
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except (OSError, ValueError):
        return str(path)


def clean_target(raw: str) -> str:
    """Remove an optional Markdown title, query, and fragment from a target."""
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        # A link title follows whitespace. Source paths in these books do not.
        target = target.split(maxsplit=1)[0]
    return unquote(target.split("#", 1)[0].split("?", 1)[0])


def markdown_targets(markdown_path: Path, visible_text: str) -> list[Path]:
    """Resolve local .md links found outside fenced code blocks."""
    targets: list[Path] = []
    for match in MARKDOWN_LINK.finditer(visible_text):
        raw = match.group(1).strip()
        lowered = raw.lower()
        if lowered.startswith(
            ("http://", "https://", "mailto:", "tel:", "data:", "javascript:", "#", "//")
        ):
            continue

        target = clean_target(raw)
        if not target or target.startswith("/") or not target.lower().endswith(".md"):
            # Absolute deployment links and generated .html links cannot be checked
            # against the source tree. Chapter-to-chapter source links use .md.
            continue
        targets.append((markdown_path.parent / target).resolve())
    return targets


def visible_markdown(text: str) -> tuple[str, str | None]:
    """Return text outside fenced code and describe an unclosed fence, if any."""
    visible: list[str] = []
    active_char: str | None = None
    active_length = 0

    for line in text.splitlines():
        match = FENCE_LINE.match(line)
        if active_char is None:
            if match:
                fence = match.group(1)
                active_char = fence[0]
                active_length = len(fence)
            else:
                visible.append(line)
            continue

        if match:
            fence = match.group(1)
            trailing = match.group(2).strip()
            if fence[0] == active_char and len(fence) >= active_length and not trailing:
                active_char = None
                active_length = 0

    unclosed = None if active_char is None else active_char * active_length
    return "\n".join(visible), unclosed


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def check_book(book_root: Path) -> BookResult:
    root = book_root.resolve()
    result = BookResult(root=root)
    source_root = root / "src"
    summary = source_root / "SUMMARY.md"

    if not root.is_dir():
        result.errors.append(f"书目录不存在: {display_path(root)}")
        return result
    if not (root / "book.toml").is_file():
        result.errors.append(f"缺少 book.toml: {display_path(root / 'book.toml')}")
    if not source_root.is_dir():
        result.errors.append(f"缺少 src 目录: {display_path(source_root)}")
        return result

    all_chapters = sorted(
        path.resolve()
        for path in source_root.rglob("*.md")
        if path.resolve() != summary.resolve()
    )
    result.chapters = len(all_chapters)

    summary_targets: list[Path] = []
    if not summary.is_file():
        result.errors.append(f"缺少 SUMMARY.md: {display_path(summary)}")
    else:
        summary_text = summary.read_text(encoding="utf-8")
        visible_summary, unclosed = visible_markdown(summary_text)
        if unclosed:
            result.errors.append(
                f"SUMMARY.md 存在未闭合的 {unclosed} 代码围栏: {display_path(summary)}"
            )
        summary_targets = markdown_targets(summary, visible_summary)

    target_counts = Counter(summary_targets)
    for target, count in sorted(target_counts.items(), key=lambda item: str(item[0])):
        if count > 1:
            result.errors.append(
                f"SUMMARY.md 重复链接同一章节 {count} 次: {display_path(target)}"
            )

    summary_chapters = set(summary_targets)
    result.listed_chapters = len(summary_chapters)
    for target in sorted(summary_chapters):
        if not is_within(target, source_root.resolve()):
            result.errors.append(f"SUMMARY.md 章节链接越出 src: {display_path(target)}")
        elif not target.is_file():
            result.errors.append(f"SUMMARY.md 章节链接不存在: {display_path(target)}")

    for chapter in sorted(set(all_chapters) - summary_chapters):
        result.errors.append(f"章节未加入 SUMMARY.md: {display_path(chapter)}")

    for chapter in all_chapters:
        text = chapter.read_text(encoding="utf-8")
        visible_text, unclosed = visible_markdown(text)
        nonblank = [line for line in visible_text.splitlines() if line.strip()]
        h1_lines = [line for line in visible_text.splitlines() if re.match(r"^#\s+\S", line)]

        if len(nonblank) < 12:
            result.errors.append(
                f"章节疑似占位页（少于 12 个非空行）: {display_path(chapter)}"
            )
        if len(h1_lines) != 1:
            result.errors.append(
                f"章节应恰好包含一个一级标题，当前为 {len(h1_lines)}: "
                f"{display_path(chapter)}"
            )
        if nonblank and not nonblank[0].startswith("# "):
            result.errors.append(f"章节首个非空行应为一级标题: {display_path(chapter)}")
        if DRAFT_MARKER.search(visible_text):
            result.warnings.append(f"发现草稿标记，请人工确认: {display_path(chapter)}")
        if unclosed:
            result.errors.append(
                f"存在未闭合的 {unclosed} 代码围栏: {display_path(chapter)}"
            )
        if visible_text.count("<details") != visible_text.count("</details>"):
            result.errors.append(f"<details> 折叠块未成对闭合: {display_path(chapter)}")

        for target in markdown_targets(chapter, visible_text):
            if not target.is_file():
                result.errors.append(
                    f"内部 Markdown 链接不存在: "
                    f"{display_path(chapter)} -> {display_path(target)}"
                )

    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "检查 mdBook 的 SUMMARY、孤立章节、内部 Markdown 链接、H1、"
            "代码围栏和草稿标记。默认检查 books/rust-hft 与 books/ai。"
        )
    )
    parser.add_argument(
        "book_roots",
        nargs="*",
        metavar="BOOK_ROOT",
        help="可选的一个或多个 mdBook 根目录（其中应包含 book.toml 与 src/）",
    )
    return parser.parse_args(argv)


def requested_roots(arguments: argparse.Namespace) -> list[Path]:
    raw_roots = (
        [Path(raw).expanduser() for raw in arguments.book_roots]
        if arguments.book_roots
        else list(DEFAULT_BOOK_ROOTS)
    )
    roots: list[Path] = []
    seen: set[Path] = set()
    for raw in raw_roots:
        root = (Path.cwd() / raw).resolve() if not raw.is_absolute() else raw.resolve()
        if root not in seen:
            roots.append(root)
            seen.add(root)
    return roots


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    results = [check_book(root) for root in requested_roots(arguments)]

    total_chapters = 0
    total_listed = 0
    total_warnings = 0
    total_errors = 0

    for result in results:
        total_chapters += result.chapters
        total_listed += result.listed_chapters
        total_warnings += len(result.warnings)
        total_errors += len(result.errors)

        print(f"\n=== {display_path(result.root)} ===")
        print(
            f"章节 {result.chapters}；SUMMARY 收录 {result.listed_chapters}；"
            f"警告 {len(result.warnings)}；错误 {len(result.errors)}"
        )
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("结果: PASS" if not result.errors else "结果: FAIL")

    print("\n=== 总计 ===")
    print(
        f"书 {len(results)}；章节 {total_chapters}；SUMMARY 收录 {total_listed}；"
        f"警告 {total_warnings}；错误 {total_errors}"
    )

    if total_errors:
        print("Book structure check failed.", file=sys.stderr)
        return 1

    print("All book structure checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
