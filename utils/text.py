from functools import lru_cache
import re
import tiktoken


@lru_cache(maxsize=32)
def get_tokenizer(model: str):
    try:
        encoding = tiktoken.encoding_for_model(model)
        return encoding.encode
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
        return encoding.encode


def count_tokens(text: str, model: str = "gpt-4") -> int:
    tokenizer = get_tokenizer(model)

    if tokenizer:
        return len(tokenizer(text))

    return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def truncate_text(
    text: str,
    model: str,
    max_tokens: int,
    suffix: str = "\n... [truncated]",
    preserve_lines: bool = True,
):
    current_tokens = count_tokens(text, model)
    if current_tokens <= max_tokens:
        return text

    suffix_tokens = count_tokens(suffix, model)
    target_tokens = max_tokens - suffix_tokens

    if target_tokens <= 0:
        return suffix.strip()

    if preserve_lines:
        return _truncate_by_lines(text, target_tokens, suffix, model)
    else:
        return _truncate_by_chars(text, target_tokens, suffix, model)


def _truncate_by_lines(text: str, target_tokens: int, suffix: str, model: str) -> str:
    lines = text.split("\n")
    result_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line + "\n", model)
        if current_tokens + line_tokens > target_tokens:
            break
        result_lines.append(line)
        current_tokens += line_tokens

    if not result_lines:
        # Fall back to character truncation if no complete lines fit
        return _truncate_by_chars(text, target_tokens, suffix, model)

    return "\n".join(result_lines) + suffix


def _truncate_by_chars(text: str, target_tokens: int, suffix: str, model: str) -> str:
    # Binary search for the right length
    low, high = 0, len(text)

    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(text[:mid], model) <= target_tokens:
            low = mid
        else:
            high = mid - 1

    return text[:low] + suffix


def clean_created_content(content: str) -> str:
    """
    Clean content for newly created files by stripping unified diff artifacts
    (e.g. @@ hunk headers, diff '+' prefixes, markdown code fence blocks, or SEARCH/REPLACE blocks)
    that LLMs frequently output when generating new files.
    """
    if not content:
        return ""

    lines = content.splitlines()

    # Strip leading empty lines
    while lines and not lines[0].strip():
        lines.pop(0)

    # Check if wrapped in SEARCH / REPLACE block
    if lines and re.match(r"^<{7}\s*SEARCH\s*$", lines[0].strip()):
        sep_idx = -1
        for idx, line in enumerate(lines):
            if re.match(r"^={7}\s*$", line.strip()):
                sep_idx = idx
                break
        if sep_idx != -1:
            lines = lines[sep_idx + 1 :]
            if lines and re.match(r"^>{7}\s*REPLACE\s*$", lines[-1].strip()):
                lines.pop()

    # Strip leading markdown code fences e.g. ```python or ```
    if lines and lines[0].strip().startswith("```"):
        lines.pop(0)
        if lines and lines[-1].strip() == "```":
            lines.pop()

    had_diff_header = False

    # Strip diff header lines like --- a/file or --- /dev/null, +++ b/file
    while lines and (
        re.match(r"^---\s+\S+", lines[0].strip())
        or re.match(r"^\+\+\+\s+\S+", lines[0].strip())
    ):
        had_diff_header = True
        lines.pop(0)

    # Strip leading unified diff hunk headers (e.g. "@@", "@@ -0,0 +1,5 @@", "@@ ... @@", "@@ -1,5 +1,5 @@ foo")
    while lines and (
        lines[0].strip().startswith("@@")
        or re.match(r"^@@(?:\s*-\d+.*|\s*.*@@.*)?$", lines[0].strip())
    ):
        had_diff_header = True
        lines.pop(0)

    # Strip any secondary markdown code fence if diff was inside fences
    if lines and lines[0].strip().startswith("```"):
        lines.pop(0)
        if lines and lines[-1].strip() == "```":
            lines.pop()

    # If diff headers were detected and all remaining non-empty lines start with '+', strip '+'
    non_empty = [l for l in lines if l.strip()]
    if non_empty and all(l.startswith("+") for l in non_empty):
        # If we had diff headers, or if lines look like code rather than a '+' bullet list
        if had_diff_header or any(
            re.match(
                r"^\+(?:def |import |from |class |const |let |var |function |<\?php|#include|package |/\*|\{|\}|\[|\])",
                l,
            )
            for l in non_empty
        ):
            lines = [l[1:] if l.startswith("+") else l for l in lines]

    # Strip any trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)

