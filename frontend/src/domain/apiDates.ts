const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

export function kstDateAt(offset = 0, now = new Date()) {
  return new Date(now.getTime() + KST_OFFSET_MS + offset * DAY_MS).toISOString().slice(0, 10);
}

export function isIsoDate(date: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  const parsed = new Date(date + 'T00:00:00Z');
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date;
}

export function recommendationRangeError(from: string, to: string, now = new Date()) {
  if (!isIsoDate(from) || !isIsoDate(to)) return '시작일과 종료일을 선택해 주세요.';
  if (from > to) return '종료일은 시작일과 같거나 이후여야 해요.';
  if (from < kstDateAt(0, now) || to > kstDateAt(29, now)) return '한국 시간 기준 오늘부터 30일 이내만 추천할 수 있어요.';
  return null;
}

export function calendarTimes(date: string, hour: number) {
  if (!isIsoDate(date) || !Number.isInteger(hour) || hour < 9 || hour > 18) return null;
  const start = Date.parse(date + 'T' + String(hour).padStart(2, '0') + ':00:00+09:00');
  return { start, end: start + 60 * 60 * 1000 };
}
