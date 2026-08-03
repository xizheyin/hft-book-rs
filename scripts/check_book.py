#!/usr/bin/env python3
"""Fast, dependency-free structural checks for this mdBook."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SUMMARY = SRC / "SUMMARY.md"

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
DRAFT_MARKER = re.compile(r"\b(?:TODO|TBD|FIXME|WIP)\b|待补充|占位内容", re.IGNORECASE)


def clean_target(raw: str) -> str:
    """Remove an optional title, query, and fragment from a Markdown target."""
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        # Markdown link titles follow whitespace. Paths in this project do not.
        target = target.split(maxsplit=1)[0]
    return unquote(target.split("#", 1)[0].split("?", 1)[0])


def markdown_targets(path: Path) -> list[Path]:
    text = path.read_text(encoding="utf-8")
    targets: list[Path] = []
    for match in MARKDOWN_LINK.finditer(text):
        raw = match.group(1).strip()
        if raw.startswith(("http://", "https://", "mailto:", "#", "javascript:")):
            continue
        target = clean_target(raw)
        if not target or not target.lower().endswith(".md"):
            continue
        targets.append((path.parent / target).resolve())
    return targets


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def without_fenced_code(text: str) -> str:
    """Return Markdown outside triple-backtick/tilde fenced code blocks."""
    visible: list[str] = []
    active_fence: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        if marker:
            if active_fence is None:
                active_fence = marker
            elif active_fence == marker:
                active_fence = None
            continue
        if active_fence is None:
            visible.append(line)
    return "\n".join(visible)


def unclosed_fence(text: str) -> str | None:
    active_fence: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        if marker and active_fence is None:
            active_fence = marker
        elif marker == active_fence:
            active_fence = None
    return active_fence


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not SUMMARY.exists():
        print("ERROR: src/SUMMARY.md 不存在", file=sys.stderr)
        return 1

    all_chapters = sorted(path.resolve() for path in SRC.rglob("*.md") if path != SUMMARY)
    summary_target_list = markdown_targets(SUMMARY)
    summary_chapters = set(summary_target_list)

    if len(summary_target_list) != len(summary_chapters):
        errors.append("SUMMARY.md 中存在重复章节链接")

    for target in sorted(summary_chapters):
        if not target.is_file():
            errors.append(f"目录链接不存在: {relative(target)}")

    orphaned = sorted(set(all_chapters) - summary_chapters)
    for path in orphaned:
        errors.append(f"章节未加入 SUMMARY.md: {relative(path)}")

    for path in all_chapters:
        text = path.read_text(encoding="utf-8")
        visible_text = without_fenced_code(text)
        nonblank = [line for line in visible_text.splitlines() if line.strip()]
        h1_lines = [line for line in visible_text.splitlines() if re.match(r"^#\s+\S", line)]

        if len(nonblank) < 12:
            errors.append(f"章节疑似占位页（少于 12 个非空行）: {relative(path)}")
        if len(h1_lines) != 1:
            errors.append(f"章节应恰好包含一个一级标题，当前为 {len(h1_lines)}: {relative(path)}")
        if nonblank and not nonblank[0].startswith("# "):
            errors.append(f"章节首个非空行应为一级标题: {relative(path)}")
        if DRAFT_MARKER.search(visible_text):
            warnings.append(f"发现草稿标记，请人工确认: {relative(path)}")
        if marker := unclosed_fence(text):
            errors.append(f"存在未闭合的 {marker} 代码围栏: {relative(path)}")
        if visible_text.count("<details") != visible_text.count("</details>"):
            errors.append(f"<details> 折叠块未成对闭合: {relative(path)}")

        for target in markdown_targets(path):
            if not target.is_file():
                errors.append(
                    f"内部 Markdown 链接不存在: {relative(path)} -> {relative(target)}"
                )

    print(
        f"Checked {len(all_chapters)} chapters; "
        f"{len(summary_chapters)} are listed in SUMMARY.md."
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print(f"Book check failed with {len(errors)} error(s).", file=sys.stderr)
        return 1

    print("Book structure check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
