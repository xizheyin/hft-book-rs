#!/usr/bin/env python3
"""Check that explicit mdBook questions have matching answers.

The checker intentionally does not treat every question mark as an exercise.  It
only enters sections whose headings advertise questions, exercises, self-tests,
or mock exams, plus files whose names explicitly identify a question bank or a
mock exam.  This keeps rhetorical questions in ordinary prose out of the report.

Supported layouts are documented by the predicates below:

* numbered or bulleted questions followed by an answer/details block;
* ``Q1``/``练习 1``/``追问`` headings with an inline answer;
* a later numbered ``参考答案`` section;
* question-bank tables whose answer/expectation is in another column;
* mock-exam labels such as ``A1`` whose later answer heading uses the same label.

The implementation is dependency-free and scans only chapters linked by the
book's SUMMARY.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOK_ROOTS = (
    REPOSITORY_ROOT / "books" / "rust-hft",
    REPOSITORY_ROOT / "books" / "ai",
)

SUMMARY_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)\n]+)\)")
FENCE_LINE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_ITEM = re.compile(r"^\s{0,3}(\d+)[.)]\s+(.+\S)\s*$")
BULLET_ITEM = re.compile(r"^\s{0,3}[-*+]\s+(.+\S)\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")
INLINE_BOLD_QUESTION = re.compile(
    r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?\*\*(?P<question>[^*]+[?？])\*\*"
    r"\s*(?P<answer>.*\S)?\s*$"
)

ANSWER_WORDS = re.compile(r"参考答|参考程序|答案|解答|解析|题解|思路")
QUESTION_SECTION_WORDS = re.compile(
    r"思考题|计算题|自测|练习|推演题|章末问题|章末面试问题|"
    r"开放追问|常见追问|高频追问|面试追问|快问快答|高频问答|面试高频|"
    r"问题库|题库|模拟笔试|模拟面试|模拟卷|盲测卷|母题"
)
QUESTION_HEADING = re.compile(
    r"^(?:Q\s*\d+\b|问[：:]|追问\s*\d*\s*[：:]|"
    r"练习\s*(?:[A-Z]|\d+)|[A-Z]\d+[.)：:]|\d+[.)]\s+.*[?？])",
    re.IGNORECASE,
)
STRICT_LIST_SECTION = re.compile(
    r"思考题|计算题|自测|(?:^|[.、：:\s])(?:进阶)?练习(?:题)?(?:$|[：:\s与])|"
    r"推演题|章末问题|章末面试问题|开放追问|常见追问"
)
MOCK_LABEL = re.compile(r"\b([A-Z]\d+)\b")
QUESTION_BANK_NAME = re.compile(r"question[_-]?bank|mock[_-]?(?:exam|test)", re.I)

# Deliberately small and visible.  These are structural, not content, exceptions.
# A question-bank table row is considered solved when it has a non-empty
# expectation/answer column; its prose is the answer, not a separate details tag.
STRUCTURAL_EXCEPTIONS = {
    "question_bank_table": (
        "题库表格的一行若至少有题目列和非空答题要点列，则按行内完整问答处理。"
    ),
    "mock_exam_label": (
        "完整模拟卷允许题目 A1/C2 与后置的 A1/C2 参考答案按标签匹配。"
    ),
}


@dataclass(frozen=True)
class Heading:
    line_index: int
    line_number: int
    level: int
    title: str
    end_index: int


@dataclass
class Question:
    path: Path
    line: int
    text: str
    answered: bool
    rule: str


@dataclass
class BookResult:
    root: Path
    chapters: int = 0
    questions: list[Question] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def solved(self) -> int:
        return sum(question.answered for question in self.questions)

    @property
    def missing(self) -> list[Question]:
        return [question for question in self.questions if not question.answered]


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except (OSError, ValueError):
        return str(path)


def clean_link_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    return unquote(target.split("#", 1)[0].split("?", 1)[0])


def visible_lines(text: str) -> list[str]:
    """Hide fenced code syntax while preserving source line numbers."""
    result: list[str] = []
    active_char: str | None = None
    active_length = 0
    for line in text.splitlines():
        match = FENCE_LINE.match(line)
        if active_char is None:
            if match:
                fence = match.group(1)
                active_char = fence[0]
                active_length = len(fence)
                # Preserve evidence that a fenced implementation exists while
                # hiding its headings, list syntax, and question marks from the
                # Markdown question parser.
                result.append("[fenced code block]")
            else:
                result.append(line)
            continue
        result.append("")
        if match:
            fence = match.group(1)
            if (
                fence[0] == active_char
                and len(fence) >= active_length
                and not match.group(2).strip()
            ):
                active_char = None
                active_length = 0
    return result


def summary_chapters(book_root: Path) -> tuple[list[Path], list[str]]:
    summary = book_root / "src" / "SUMMARY.md"
    if not summary.is_file():
        return [], [f"缺少 SUMMARY.md: {display_path(summary)}"]

    lines = visible_lines(summary.read_text(encoding="utf-8"))
    chapters: list[Path] = []
    errors: list[str] = []
    seen: set[Path] = set()
    for line in lines:
        for match in SUMMARY_LINK.finditer(line):
            target = clean_link_target(match.group(1))
            if not target or not target.lower().endswith(".md"):
                continue
            chapter = (summary.parent / target).resolve()
            if chapter in seen:
                continue
            seen.add(chapter)
            if not chapter.is_file():
                errors.append(f"SUMMARY 章节不存在: {display_path(chapter)}")
            else:
                chapters.append(chapter)
    return chapters, errors


def parse_headings(lines: list[str]) -> list[Heading]:
    raw: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            raw.append((index, len(match.group(1)), match.group(2).strip()))

    headings: list[Heading] = []
    for position, (index, level, title) in enumerate(raw):
        end = len(lines)
        for next_index, next_level, _ in raw[position + 1 :]:
            if next_level <= level:
                end = next_index
                break
        headings.append(Heading(index, index + 1, level, title, end))
    return headings


def is_answer_heading(title: str) -> bool:
    return bool(ANSWER_WORDS.search(title)) and not title.startswith("做题方法")


def is_question_section(title: str) -> bool:
    # Some chapters intentionally combine questions and answers in one section,
    # e.g. "面试追问与参考答法" or "练习与参考答案".  A pure
    # "常见追问参考答案" section, however, is answer-only.
    if re.search(r"追问与参考答法|练习.*参考答案", title):
        return True
    if is_answer_heading(title):
        return False
    return bool(QUESTION_SECTION_WORDS.search(title))


def explicit_question_heading(title: str, in_question_section: bool) -> bool:
    if is_answer_heading(title):
        return False
    if QUESTION_HEADING.search(title):
        return True
    if in_question_section and title.endswith(("?", "？")):
        return True
    return False


def details_ranges(lines: list[str]) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    stack: list[int] = []
    for index, line in enumerate(lines):
        if "<details" in line:
            stack.append(index)
        if "</details>" in line and stack:
            start = stack.pop()
            ranges.append((start, index + 1, "\n".join(lines[start : index + 1])))
    return ranges


def range_has_answer_details(
    start: int, end: int, details: list[tuple[int, int, str]]
) -> bool:
    for detail_start, detail_end, payload in details:
        if start <= detail_start < end:
            # A summary is merely the answer block's label.  Do not let a
            # verbose ``<summary>`` make an otherwise empty details shell pass.
            body = re.sub(
                r"<summary\b[^>]*>.*?</summary>",
                " ",
                payload,
                flags=re.IGNORECASE | re.DOTALL,
            )
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s+", " ", body).strip()
            # The block is already immediately attached to an explicit
            # question, so neutral summaries such as "验收参考" and
            # "展开完整实现" are valid.  Requiring the literal word 答案
            # would reject code exercises and worked verification processes.
            if detail_end - detail_start >= 3 and len(body) >= 12:
                return True
    return False


def extract_mock_answer_labels(lines: list[str], headings: list[Heading]) -> set[str]:
    """Collect globally unique A1/C2-style labels from mock-exam answers."""
    labels: set[str] = set()
    for heading in headings:
        if is_answer_heading(heading.title):
            for label in MOCK_LABEL.findall(heading.title.upper()):
                labels.add(label)

            for line in lines[heading.line_index : heading.end_index]:
                for label in MOCK_LABEL.findall(line.upper()):
                    if ANSWER_WORDS.search(line):
                        labels.add(label)

    return labels


def answer_item_keys(
    lines: list[str], answer_range: tuple[int, int] | None
) -> set[str]:
    """Return numeric answer keys only from one question section's answer range."""
    if answer_range is None:
        return set()
    start, end = answer_range
    keys: set[str] = set()
    for line in lines[start:end]:
        item = NUMBERED_ITEM.match(line)
        if item and len(re.sub(r"[*_`]", "", item.group(2)).strip()) >= 8:
            keys.add(item.group(1))
        exercise = re.search(r"第\s*(\d+)\s*题", line)
        if exercise and ANSWER_WORDS.search(line):
            keys.add(exercise.group(1))
    return keys


def details_answer_item_keys(
    start: int, end: int, details: list[tuple[int, int, str]]
) -> set[str]:
    """Collect numbered answers from details blocks inside one question section."""
    keys: set[str] = set()
    for detail_start, _, payload in details:
        if not start <= detail_start < end:
            continue
        for line in visible_lines(payload):
            item = NUMBERED_ITEM.match(line)
            if item and len(re.sub(r"[*_`]", "", item.group(2)).strip()) >= 8:
                keys.add(item.group(1))
    return keys


def substantive_inline_answer(lines: list[str], start: int, end: int) -> bool:
    pieces: list[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "<details", "</details", "<summary")):
            continue
        if stripped.startswith((">", "-", "*")) and stripped.endswith(("?", "？")):
            continue
        pieces.append(re.sub(r"[*_`>#|]", "", stripped))
    return len("".join(pieces)) >= 18


def enclosing_question_section(
    line_index: int, headings: list[Heading]
) -> Heading | None:
    candidates = [
        heading
        for heading in headings
        if heading.line_index < line_index < heading.end_index
        and is_question_section(heading.title)
    ]
    return max(candidates, key=lambda heading: heading.level, default=None)


def associated_answer_range(
    section: Heading, headings: list[Heading]
) -> tuple[int, int] | None:
    # Prefer a child answer subsection.
    children = [
        heading
        for heading in headings
        if section.line_index < heading.line_index < section.end_index
        and is_answer_heading(heading.title)
    ]
    if children:
        first = min(children, key=lambda heading: heading.line_index)
        return first.line_index, first.end_index

    # Otherwise accept the immediately following sibling answer section.
    later = [heading for heading in headings if heading.line_index > section.line_index]
    for heading in sorted(later, key=lambda item: item.line_index):
        if heading.level < section.level:
            break
        if heading.level == section.level:
            if is_answer_heading(heading.title):
                return heading.line_index, heading.end_index
            break
    return None


def answer_item_count(lines: list[str], answer_range: tuple[int, int] | None) -> int:
    if answer_range is None:
        return 0
    start, end = answer_range
    numbered = {
        match.group(1)
        for line in lines[start:end]
        if (match := NUMBERED_ITEM.match(line))
        and len(re.sub(r"[*_`]", "", match.group(2)).strip()) >= 8
    }
    if numbered:
        return len(numbered)
    bullets = [
        match.group(1)
        for line in lines[start:end]
        if (match := BULLET_ITEM.match(line))
        and len(re.sub(r"[*_`]", "", match.group(1)).strip()) >= 8
    ]
    return len(bullets)


def scan_markdown(path: Path, text: str) -> list[Question]:
    """Scan one Markdown document; separated from I/O for focused tests."""
    lines = visible_lines(text)
    headings = parse_headings(lines)
    details = details_ranges(lines)
    mock_answer_labels = extract_mock_answer_labels(lines, headings)
    special_document = bool(QUESTION_BANK_NAME.search(path.stem))

    questions: list[Question] = []
    seen_lines: set[int] = set()

    # Heading-shaped questions: Q17, 练习 A, 追问, and mock labels.
    for heading in headings:
        section = enclosing_question_section(heading.line_index, headings)
        in_section = section is not None or special_document
        standalone_problem = bool(re.search(r"母题|综合练习", heading.title))
        if not explicit_question_heading(heading.title, in_section):
            # Mock exams use A1/C2 headings without a literal question mark.
            if not (
                special_document
                and MOCK_LABEL.match(heading.title.upper())
                and not is_answer_heading(heading.title)
            ) and not standalone_problem:
                continue

        local_details = range_has_answer_details(
            heading.line_index + 1, heading.end_index, details
        )
        labels = MOCK_LABEL.findall(heading.title.upper())
        mock_answer = bool(
            labels and any(label in mock_answer_labels for label in labels)
        )
        exercise_heading = heading.title.startswith("练习")
        inline_answer = substantive_inline_answer(
            lines, heading.line_index + 1, heading.end_index
        )
        answered = local_details or mock_answer or (inline_answer and not exercise_heading)
        rule = (
            "相邻折叠答案"
            if local_details
            else "后置同标签答案"
            if mock_answer
            else "标题下行内答案"
            if answered
            else "未找到标题对应答案"
        )
        questions.append(
            Question(path, heading.line_number, heading.title, answered, rule)
        )
        seen_lines.add(heading.line_index)

    # Explicit question sections containing numbered/bulleted exercises.
    for section in headings:
        if not is_question_section(section.title):
            continue
        if not STRICT_LIST_SECTION.search(section.title) or is_answer_heading(section.title):
            continue
        answer_range = associated_answer_range(section, headings)
        local_answer_keys = answer_item_keys(lines, answer_range)
        local_details_keys = details_answer_item_keys(
            section.line_index + 1, section.end_index, details
        )
        answer_count = answer_item_count(lines, answer_range)
        candidates: list[tuple[int, str, str | None]] = []
        in_details = 0
        in_child_answer = False
        for index in range(section.line_index + 1, section.end_index):
            line = lines[index]
            if "<details" in line:
                in_details += 1
            if "</details>" in line:
                in_details = max(0, in_details - 1)
                continue
            heading_match = HEADING.match(line)
            if heading_match:
                title = heading_match.group(2).strip()
                in_child_answer = is_answer_heading(title)
                continue
            if in_details or in_child_answer or index in seen_lines:
                continue

            # A nested subsection owns its own questions.  This prevents an
            # outer "question bank" or mock-exam section from mistaking an
            # answer's numbered reasoning steps for additional exercises.
            nested = [
                heading
                for heading in headings
                if section.line_index < heading.line_index < index < heading.end_index
                and heading.level > section.level
            ]
            if nested:
                continue

            numbered = NUMBERED_ITEM.match(line)
            if numbered:
                if INLINE_BOLD_QUESTION.match(line):
                    continue
                candidates.append((index, numbered.group(2), numbered.group(1)))
                continue
            bullet = BULLET_ITEM.match(line)
            if (
                bullet
                and bullet.group(1).rstrip().endswith(("?", "？"))
                and not INLINE_BOLD_QUESTION.match(line)
            ):
                candidates.append((index, bullet.group(1), None))

        for ordinal, (index, text, key) in enumerate(candidates, start=1):
            if index in seen_lines:
                continue
            next_index = (
                candidates[ordinal][0] if ordinal < len(candidates) else section.end_index
            )
            direct = range_has_answer_details(index + 1, next_index, details)
            keyed = key is not None and key in local_answer_keys
            details_keyed = key is not None and key in local_details_keys
            grouped = answer_count >= len(candidates) > 0
            answered = direct or keyed or details_keyed or grouped
            rule = (
                "题后折叠答案"
                if direct
                else "同编号答案区"
                if keyed
                else "题区折叠答案编号"
                if details_keyed
                else "等长答案列表"
                if grouped
                else "未找到列表题答案"
            )
            questions.append(Question(path, index + 1, text, answered, rule))
            seen_lines.add(index)

    # Inline bold Q&A, used by compact interview follow-up sections.
    for index, line in enumerate(lines):
        if index in seen_lines:
            continue
        match = INLINE_BOLD_QUESTION.match(line)
        if not match:
            continue
        section = enclosing_question_section(index, headings)
        if section is None:
            continue
        answer = (match.group("answer") or "").strip()
        if not answer:
            end = len(lines)
            for later in range(index + 1, len(lines)):
                if HEADING.match(lines[later]) or INLINE_BOLD_QUESTION.match(lines[later]):
                    end = later
                    break
            answered = substantive_inline_answer(lines, index + 1, end)
        else:
            answered = len(re.sub(r"[*_`]", "", answer)) >= 8
        questions.append(
            Question(
                path,
                index + 1,
                match.group("question"),
                answered,
                "加粗行内答案" if answered else "加粗问题后缺少行内答案",
            )
        )
        seen_lines.add(index)

    # Table question banks: the first column names the oral question/theme and
    # the second column is already an inline answer/expected explanation.
    if special_document:
        active_question_table = False
        for index, line in enumerate(lines):
            if not line.strip().startswith("|"):
                active_question_table = False
                continue
            if TABLE_SEPARATOR.match(line):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 2 or any("---" in cell for cell in cells):
                continue
            if cells[0] in {"口试主题", "题目", "问题", "场景"}:
                active_question_table = True
                continue
            if not active_question_table:
                continue
            answered = len(re.sub(r"[*_`]", "", cells[1])) >= 8
            questions.append(
                Question(
                    path,
                    index + 1,
                    cells[0],
                    answered,
                    "题库表格行内答案" if answered else "题库表格答案列为空",
                )
            )

    return sorted(questions, key=lambda question: (question.line, question.text))


def scan_chapter(path: Path) -> list[Question]:
    return scan_markdown(path, path.read_text(encoding="utf-8"))


def scan_book(book_root: Path) -> BookResult:
    root = book_root.resolve()
    result = BookResult(root=root)
    if not root.is_dir():
        result.errors.append(f"书目录不存在: {display_path(root)}")
        return result
    chapters, errors = summary_chapters(root)
    result.errors.extend(errors)
    result.chapters = len(chapters)
    for chapter in chapters:
        try:
            result.questions.extend(scan_chapter(chapter))
        except (OSError, UnicodeError) as error:
            result.errors.append(f"无法读取 {display_path(chapter)}: {error}")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "检查 mdBook SUMMARY 收录章节中的显式题目是否有匹配答案；"
            "默认检查 books/rust-hft 与 books/ai。"
        )
    )
    parser.add_argument(
        "book_roots",
        nargs="*",
        metavar="BOOK_ROOT",
        help="一个或多个包含 book.toml 与 src/SUMMARY.md 的书根目录",
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
    results = [scan_book(root) for root in requested_roots(arguments)]

    total_questions = 0
    total_solved = 0
    total_missing = 0
    total_errors = 0
    for result in results:
        total_questions += len(result.questions)
        total_solved += result.solved
        total_missing += len(result.missing)
        total_errors += len(result.errors)
        print(f"\n=== {display_path(result.root)} ===")
        print(
            f"SUMMARY 章节 {result.chapters}；题目 {len(result.questions)}；"
            f"已解 {result.solved}；缺失 {len(result.missing)}"
        )
        for error in result.errors:
            print(f"错误: {error}")
        for question in result.missing:
            print(
                f"缺失: {display_path(question.path)}:{question.line}: "
                f"{question.text}（{question.rule}）"
            )

    print("\n=== 总计 ===")
    print(
        f"书 {len(results)}；题目 {total_questions}；已解 {total_solved}；"
        f"缺失 {total_missing}；结构错误 {total_errors}"
    )
    if total_missing or total_errors:
        print("结果: FAIL")
        return 1
    print("结果: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
