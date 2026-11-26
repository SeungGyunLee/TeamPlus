"""집현전 API 실제 응답 형식 확인 스크립트 (학교 비공개 API, 사용 전 확인 필요).

학교 서버를 딱 2번만 부른다 (방별 현황 1번 + 예약 가능 맵 1번).
받은 원본 XML은 backend/.probe/ 에 저장한다 (.gitignore에 있어서 커밋되지 않음).

사용법 (backend 폴더에서, backend/.env에 JIPHYEONJEON_STATUS_URL·JIPHYEONJEON_MAP_URL 설정 후):
    python scripts/probe_jiphyeonjeon.py                # 첫 번째 종류(4인실), 오늘
    python scripts/probe_jiphyeonjeon.py 6 2026-11-19   # 종류 번호(4·6·10), 날짜 지정

출력의 '시간 × 방' 표를 도서관 앱의 같은 날짜 화면과 비교해서 맞는지 확인한다.
(가능 = 값 0, 예약됨 = 5, 사용중 = 7, 지남 = 10. 형식 설명은 app/places/jiphyeonjeon.py 맨 위)
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.places.jiphyeonjeon import (  # noqa: E402
    CODE_LABELS,
    JiphyeonjeonClient,
    JiphyeonjeonFormatError,
    leaf_fields,
    parse_map_codes,
    parse_room_status,
)

OUT = Path(__file__).resolve().parent.parent / ".probe"


def save(name: str, raw: bytes) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    path.write_bytes(raw)
    return path


def show_fields(raw: bytes, limit: int = 80) -> None:
    try:
        fields = leaf_fields(raw)
    except JiphyeonjeonFormatError as e:
        print(f"  XML로 읽지 못했어요: {e}")
        return
    for tag, value in fields[:limit]:
        print(f"  {tag} = {value!r}")
    if len(fields) > limit:
        print(f"  … 외 {len(fields) - limit}개 (전체는 저장한 파일 참고)")


def main() -> None:
    s = get_settings()
    if not (s.jiphyeonjeon_status_url and s.jiphyeonjeon_map_url):
        sys.exit("backend/.env에 JIPHYEONJEON_STATUS_URL과 JIPHYEONJEON_MAP_URL을 넣어주세요.")
    client = JiphyeonjeonClient(
        s.jiphyeonjeon_status_url,
        s.jiphyeonjeon_map_url,
        timeout=s.jiphyeonjeon_timeout_seconds,
    )
    room_arg = sys.argv[1] if len(sys.argv) > 1 else None
    day = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()

    # 1. 방별 현황
    raw = client.raw("status")
    print(f"=== 1. 방별 현황 → 저장: {save('status.xml', raw)}")
    rooms = []
    try:
        rooms = parse_room_status(raw)
        print(f"  방 {len(rooms)}개")
        for r in rooms:
            hol = f" (휴무: {r.holiday_msg or '예'})" if r.holiday else ""
            print(
                f"  room_no={r.room_no!r:8} {r.name} · 좌석 {r.total_seat} · "
                f"남음 {r.remain_seat} · 운영 {r.open_time}~{r.close_time}{hol}"
            )
    except JiphyeonjeonFormatError as e:
        print(f"  예상과 다른 형식이에요 ({e}). 원본 필드:")
        show_fields(raw)

    # 2. 예약 가능 맵
    room_no = room_arg or (rooms[0].room_no if rooms else "4")
    form = {"room_seat_no": room_no, "search_date": day.strftime("%Y%m%d")}
    raw = client.raw("map", form)
    path = save(f"map_{room_no}_{day:%Y%m%d}.xml", raw)
    print(f"\n=== 2. 예약 가능 맵 (종류 {room_no}, {day}) → 저장: {path}")
    try:
        rmap = parse_map_codes(raw)
    except JiphyeonjeonFormatError as e:
        print(f"  해석 실패: {e}\n  원본 필드:")
        show_fields(raw)
    else:
        names = ", ".join(f"{k}={v}" for k, v in rmap.names.items())
        print(f"  응답의 방 이름: {names or '없음'}")
        rooms = list(rmap.codes)
        print("  시간    " + "".join(f"{r + '실':>7}" for r in rooms))
        for i, h in enumerate(rmap.hours):
            cells = "".join(
                f"{CODE_LABELS.get(rmap.codes[r][i], '?' + rmap.codes[r][i]):>6}" for r in rooms
            )
            print(f"  {h:02d}:00 {cells}")
        if not rooms:
            print("  비어 있어요. 종류 번호(방별 현황의 room_no: 4·6·10)로 조회했는지 확인하세요.")
        print("  → 도서관 앱의 같은 날짜 화면과 방·시간별로 맞는지 확인하세요.")

    print(f"\n{OUT} 안의 xml 파일을 백엔드 담당에게 공유하면 형식을 맞출 수 있어요.")


if __name__ == "__main__":
    main()
