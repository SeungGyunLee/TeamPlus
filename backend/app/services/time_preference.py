"""프롬프트 1의 time_preference(자유 텍스트)를 코드가 해석해 시간 필터로 바꾼다.

예: "목요일 저녁", "오후 3시 이후", "주말", "11/4", "내일 2시~5시"
알아듣지 못하면 None을 돌려주고, 이 경우 시간 조건 없이 추천한다.

규칙
- 오전/오후 표시 없이 1~8시라고 하면 오후로 본다 (팀플 회의 맥락).
- 시각을 직접 말했으면 '오후/저녁' 같은 시간대 단어보다 시각을 우선한다.
- "3시"처럼 이후/전 없이 말하면 3시~4시 사이에 시작하는 구간만 허용한다.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAYS = "월화수목금토일"

# 시간대 단어 → (시작, 끝) 분
PERIODS: dict[str, tuple[int, int]] = {
    "아침": (8 * 60, 11 * 60),
    "오전": (9 * 60, 12 * 60),
    "점심": (11 * 60, 14 * 60),
    "오후": (12 * 60, 18 * 60),
    "저녁": (18 * 60, 22 * 60),
    "밤": (19 * 60, 24 * 60),
}

# "2시간"(길이)은 시각이 아니므로 (?!간)으로 제외한다.
_HOUR = r"(?:(오전|오후|저녁|밤)\s*)?(\d{1,2})\s*시(?!간)(?:\s*(반|\d{1,2}\s*분))?"
# 범위의 앞쪽은 "2~5시"처럼 '시'를 생략할 수 있다.
_HOUR_OPT = r"(?:(오전|오후|저녁|밤)\s*)?(\d{1,2})\s*시?(?!간)(?:\s*(반|\d{1,2}\s*분))?"
RANGE_RE = re.compile(_HOUR_OPT + r"\s*(?:부터|~|-|에서)\s*" + _HOUR + r"(?:\s*까지)?")
HOUR_RE = re.compile(_HOUR + r"\s*(이후|부터|넘어서|넘어|후|이전|전|까지)?")
DATE_RE = re.compile(r"(\d{1,2})\s*(?:/|월|\.)\s*(\d{1,2})\s*일?")


@dataclass(frozen=True)
class TimeFilter:
    weekdays: frozenset[int] | None = None
    dates: frozenset[date] | None = None
    start_min: int | None = None  # 이 시각 이후에 시작
    end_min: int | None = None  # 이 시각 전에 끝
    latest_start_min: int | None = None  # 이 시각까지 시작

    def allows(self, day: date, start_min: int, end_min: int) -> bool:
        if self.weekdays is not None and day.weekday() not in self.weekdays:
            return False
        if self.dates is not None and day not in self.dates:
            return False
        if self.start_min is not None and start_min < self.start_min:
            return False
        if self.end_min is not None and end_min > self.end_min:
            return False
        if self.latest_start_min is not None and start_min > self.latest_start_min:
            return False
        return True


def _to_min(prefix: str | None, hour: str, minute: str | None) -> int:
    h = int(hour)
    if prefix in ("오후", "저녁", "밤") and h < 12:
        h += 12
    elif prefix is None and 1 <= h <= 8:
        h += 12
    m = 0
    if minute:
        m = 30 if minute == "반" else int(re.sub(r"\D", "", minute))
    return h * 60 + m


def parse_time_preference(text: str | None, today: date) -> TimeFilter | None:
    if not text or not text.strip():
        return None
    s = text.strip()

    weekdays: set[int] = set()
    for ch in re.findall(r"([월화수목금토일])요일", s):
        weekdays.add(WEEKDAYS.index(ch))
    if "주말" in s:
        weekdays |= {5, 6}
    if "평일" in s:
        weekdays |= {0, 1, 2, 3, 4}

    dates: set[date] = set()
    for word, offset in (("오늘", 0), ("내일", 1), ("모레", 2)):
        if word in s:
            dates.add(today + timedelta(days=offset))

    start_min = end_min = latest_start = None

    # 날짜 숫자("11/4")와 시각 숫자가 섞이지 않게, 날짜를 먼저 찾아 지운다.
    for mo, dd in DATE_RE.findall(s):
        try:
            d = date(today.year, int(mo), int(dd))
        except ValueError:
            continue
        if d < today:
            d = date(today.year + 1, d.month, d.day)
        dates.add(d)
    rest = DATE_RE.sub(" ", s)

    found_hour = False
    m = RANGE_RE.search(rest)
    if m:
        p1, h1, mi1, p2, h2, mi2 = m.groups()
        start_min = _to_min(p1, h1, mi1)
        end_min = _to_min(p2 or p1, h2, mi2)
        if end_min <= start_min:
            end_min += 12 * 60
        rest = rest[: m.start()] + " " + rest[m.end() :]
        found_hour = True
    else:
        for prefix, hour, minute, suffix in HOUR_RE.findall(rest):
            t = _to_min(prefix or None, hour, minute or None)
            if suffix in ("이후", "부터", "넘어서", "넘어", "후"):
                start_min = t
            elif suffix in ("이전", "전", "까지"):
                end_min = t
            else:
                start_min, latest_start = t, t + 60
            found_hour = True
        rest = HOUR_RE.sub(" ", rest)

    if not found_hour:
        hits = [PERIODS[k] for k in PERIODS if k in rest]
        if hits:
            start_min = min(h[0] for h in hits)
            end_min = max(h[1] for h in hits)

    if not (weekdays or dates or start_min is not None or end_min is not None):
        return None
    return TimeFilter(
        weekdays=frozenset(weekdays) or None,
        dates=frozenset(dates) or None,
        start_min=start_min,
        end_min=end_min,
        latest_start_min=latest_start,
    )
