import re
from dataclasses import dataclass


@dataclass
class ParsedResponse:
    code: str | None
    answer: str | None


_CODE_RE = re.compile(r"<code>(.*?)</code>", re.DOTALL)
_ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)


def parse_llm_response(text: str) -> ParsedResponse:
    code_m = _CODE_RE.search(text)
    ans_m = _ANSWER_RE.search(text)
    return ParsedResponse(
        code=code_m.group(1).strip() if code_m else None,
        answer=ans_m.group(1).strip() if ans_m else None,
    )
