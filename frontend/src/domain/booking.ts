import { AppData, HOURS, ROOMS, Reservation, localDate, uid } from './model';
export type BookingInput = Pick<Reservation, 'groupId' | 'roomId' | 'date' | 'hour'>;
export function isValidDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split('-').map(Number);
  const date = new Date(y!, m! - 1, d);
  return localDate(date) === value;
}
// Stable occupancy: identical room/date/hour always returns the same result.
export function isSeedOccupied(roomId: string, date: string, hour: number) {
  let hash = 5381;
  for (const char of `${roomId}|${date}`) hash = ((hash * 33) ^ char.charCodeAt(0)) >>> 0;
  return (hash + hour * 17) % 7 < 2;
}
export function isOccupied(reservations: Reservation[], input: BookingInput) {
  return isSeedOccupied(input.roomId, input.date, input.hour) || reservations.some(r => r.status === 'active' && r.roomId === input.roomId && r.date === input.date && r.hour === input.hour);
}
export function book(data: AppData, input: BookingInput, now = new Date()): AppData {
  const room = ROOMS.find(r => r.id === input.roomId);
  const group = data.groups.find(g => g.id === input.groupId);
  if (!room || !group || !HOURS.includes(input.hour) || !isValidDate(input.date)) throw new Error('예약 정보를 다시 확인해 주세요.');
  const today = localDate(now);
  const last = new Date(now); last.setDate(last.getDate() + 29);
  if (input.date < today || input.date > localDate(last) || (input.date === today && input.hour <= now.getHours())) throw new Error('현재 이후 30일 이내의 시간을 선택해 주세요.');
  if (group.members.length > room.capacity) throw new Error('팀 인원보다 큰 인실을 선택해 주세요.');
  if (isOccupied(data.reservations, input)) throw new Error('이미 예약된 시간입니다. 다른 시간을 선택해 주세요.');
  if (data.reservations.some(r => r.status === 'active' && r.groupId === input.groupId && r.date === input.date && r.hour === input.hour)) throw new Error('이 모임은 같은 시간에 다른 예약이 있어요.');
  return { ...data, reservations: [{ ...input, id: uid(), groupName: group.name, status: 'active', createdAt: now.toISOString() }, ...data.reservations] };
}
export function cancel(data: AppData, id: string): AppData {
  return { ...data, reservations: data.reservations.map(r => r.id === id ? { ...r, status: 'cancelled' } : r) };
}
