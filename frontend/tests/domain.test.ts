import { test } from 'node:test';
import assert from 'node:assert/strict';
import { availability, rankedAvailability } from '../src/domain/availability';
import { book, cancel, isOccupied, isSeedOccupied, isValidDate } from '../src/domain/booking';
import { initialData } from '../src/data/seed';
import { decodeData, LocalRepository, StoragePort } from '../src/data/repository';
import { AppData, HOURS, ROOMS, SlotKey } from '../src/domain/model';
const NOW = new Date(2030, 0, 7, 8, 0);
const DATE = '2030-01-08';
function freeHour(room = 'J201') { return HOURS.find(h => !isSeedOccupied(room, DATE, h))!; }
test('all 30 weekly blocks partition every member accurately', () => {
  const g = initialData().groups[0]!; const slots = availability(g);
  assert.equal(slots.length, 30);
  const mondayFirst = slots.find(s => s.key === '0-0')!;
  assert.deepEqual(mondayFirst.available.map(m => m.name), ['서연']);
  assert.equal(mondayFirst.unavailable.length, 2);
  assert.equal(slots.find(s => s.key === '1-2')!.count, 0);
  for (const s of slots) assert.equal(s.available.length + s.unavailable.length, g.members.length);
});
test('ranking is descending, ties follow weekday then period', () => {
  const ranked = rankedAvailability(initialData().groups[0]!);
  for (let i = 1; i < ranked.length; i++) {
    const a = ranked[i-1]!, b = ranked[i]!;
    assert.ok(a.count >= b.count);
    if (a.count === b.count) assert.ok(a.day < b.day || (a.day === b.day && a.period < b.period));
  }
});
test('adding/removing a member updates numerator and denominator without mutating timetables', () => {
  const g = initialData().groups[0]!; const before = JSON.stringify(g);
  const changed = { ...g, members: [...g.members, { id: 'new', name: '새 팀원', busy: ['0-0'] as SlotKey[] }] };
  const after = availability(changed).find(s => s.key === '0-0')!;
  assert.equal(after.count, 1); assert.equal(after.total, 4);
  assert.equal(availability({ ...changed, members: changed.members.slice(2) }).find(s => s.key === '0-0')!.count, 1);
  assert.equal(JSON.stringify(g), before);
});
test('all-free and all-busy schedules give exact counts', () => {
  const g = initialData().groups[0]!;
  assert.ok(availability({ ...g, members: g.members.map(m => ({ ...m, busy: [] })) }).every(s => s.count === 3));
  const all = availability(g).map(s => s.key);
  assert.ok(availability({ ...g, members: g.members.map(m => ({ ...m, busy: all })) }).every(s => s.count === 0));
});
test('seeded room occupancy is deterministic and contains free and occupied slots', () => {
  const a = HOURS.map(h => isSeedOccupied('J201', DATE, h));
  assert.deepEqual(a, HOURS.map(h => isSeedOccupied('J201', DATE, h)));
  assert.ok(a.includes(true) && a.includes(false));
});
test('booking prevents duplicates and cancelling releases only the user slot', () => {
  const d = initialData(); const input = { groupId: d.groups[0]!.id, roomId: 'J201', date: DATE, hour: freeHour() };
  const booked = book(d, input, NOW);
  assert.equal(d.reservations.length, 0);
  assert.equal(booked.reservations.length, 1);
  assert.ok(isOccupied(booked.reservations, input));
  assert.throws(() => book(booked, input, NOW), /이미 예약/);
  const cancelled = cancel(booked, booked.reservations[0]!.id);
  assert.equal(cancelled.reservations[0]!.status, 'cancelled');
  assert.ok(!isOccupied(cancelled.reservations, input));
  assert.equal(book(cancelled, input, NOW).reservations.length, 2);
  const taken = HOURS.find(h => isSeedOccupied('J201', DATE, h))!;
  assert.throws(() => book(cancelled, { ...input, hour: taken }, NOW), /이미 예약/);
});
test('same group cannot occupy two rooms at the same time', () => {
  const d = initialData();
  let match: { a: string; b: string; h: number } | undefined;
  for (const a of ROOMS) for (const b of ROOMS) for (const h of HOURS) if (a.id !== b.id && !isSeedOccupied(a.id, DATE, h) && !isSeedOccupied(b.id, DATE, h)) match = { a: a.id, b: b.id, h };
  assert.ok(match);
  const input = { groupId: d.groups[0]!.id, date: DATE, hour: match.h, roomId: match.a };
  assert.throws(() => book(book(d, input, NOW), { ...input, roomId: match.b }, NOW), /다른 예약/);
});
test('booking validates room, group, capacity, date and hours', () => {
  const d = initialData(); const input = { groupId: d.groups[0]!.id, roomId: 'J201', date: DATE, hour: freeHour() };
  assert.throws(() => book(d, { ...input, roomId: 'fake' }, NOW));
  assert.throws(() => book(d, { ...input, groupId: 'fake' }, NOW));
  assert.throws(() => book(d, { ...input, hour: 24 }, NOW));
  assert.throws(() => book(d, { ...input, date: '2030-02-31' }, NOW));
  assert.throws(() => book(d, { ...input, date: '2030-01-06' }, NOW));
  assert.throws(() => book(d, { ...input, date: '2030-02-06' }, NOW));
  assert.throws(() => book(d, { ...input, date: '2030-01-07', hour: 9 }, new Date(2030,0,7,9,30)));
  const large = { ...d, groups: d.groups.map(g => ({ ...g, members: [...g.members, ...g.members.map(m => ({ ...m, id: m.id + '-2' }))] })) };
  assert.throws(() => book(large, input, NOW), /인실/);
  assert.ok(isValidDate('2032-02-29')); assert.ok(!isValidDate('2030-02-29'));
});
class MemoryStorage implements StoragePort {
  value: string | null = null; fail = false;
  async getItem() { return this.value; }
  async setItem(_key: string, value: string) { if (this.fail) throw new Error('disk full'); this.value = value; }
}
test('repository restores theme, members, timetables and reservation after restart', async () => {
  const storage = new MemoryStorage(); const repo = new LocalRepository(storage);
  const d = await repo.load();
  const input = { groupId: d.groups[0]!.id, roomId: 'J201', date: DATE, hour: freeHour() };
  const saved: AppData = { ...book(d, input, NOW), theme: 'dark' };
  saved.groups[0]!.members[0]!.name = '저장한 이름';
  await repo.save(saved);
  assert.deepEqual(await new LocalRepository(storage).load(), saved);
});
test('serialized saves preserve latest snapshot; failed writes can be retried', async () => {
  const storage = new MemoryStorage(); const repo = new LocalRepository(storage); const d = initialData();
  await Promise.all([repo.save(d), repo.save({ ...d, theme: 'dark' }), repo.save({ ...d, theme: 'system' })]);
  assert.equal((await repo.load()).theme, 'system');
  storage.fail = true; await assert.rejects(repo.save({ ...d, theme: 'dark' }));
  storage.fail = false; await repo.save({ ...d, theme: 'dark' });
  assert.equal((await repo.load()).theme, 'dark');
});
test('invalid or corrupted data is rejected rather than overwritten', async () => {
  assert.throws(() => decodeData('{bad'));
  assert.throws(() => decodeData(JSON.stringify({ ...initialData(), theme: 'broken' })));
  const d = initialData(); d.groups[0]!.members[0]!.busy = ['9-9' as SlotKey];
  assert.throws(() => decodeData(JSON.stringify(d)));
  const storage = new MemoryStorage(); storage.value = '{original-corrupt';
  await assert.rejects(new LocalRepository(storage).load()); assert.equal(storage.value, '{original-corrupt');
});

test('new-group name migration targets the correct group and preserves saved user data', async () => {
  const storage = new MemoryStorage();
  const legacy = initialData();
  legacy.seedNamesVersion = 1;
  legacy.theme = 'dark';
  const originalGroup = legacy.groups[0]!;
  originalGroup.members[0]!.name = '건우';
  originalGroup.members[1]!.name = '직접 바꾼 이름';
  originalGroup.members[2]!.name = '휘서';
  legacy.groups.push({ ...structuredClone(originalGroup), id: 'new-group', name: '새로운 모임',
    members: originalGroup.members.map((m, i) => ({ ...m, id: `new-${i}`, name: ['나', '팀원 2', '팀원 3'][i]! })) });
  legacy.groups.push({ ...structuredClone(originalGroup), id: 'custom-group', name: '다른 모임' });
  const saved = book(legacy, { groupId: originalGroup.id, roomId: 'J201', date: DATE, hour: freeHour() }, NOW);
  storage.value = JSON.stringify(saved);
  const repo = new LocalRepository(storage);
  const migrated = await repo.load();
  assert.deepEqual(migrated.groups[0]!.members.map(m => m.name), ['민서', '직접 바꾼 이름', '서연']);
  assert.deepEqual(migrated.groups[1]!.members.map(m => m.name), ['건우', '승균', '휘서']);
  assert.deepEqual(migrated.groups[1]!.members.map(m => m.busy), saved.groups[1]!.members.map(m => m.busy));
  assert.deepEqual(migrated.groups[2], saved.groups[2]);
  assert.deepEqual(migrated.reservations, saved.reservations);
  assert.equal(migrated.theme, 'dark');
  assert.equal(JSON.parse(storage.value!).seedNamesVersion, 2);
  migrated.groups[1]!.members[0]!.name = '직접 수정';
  await repo.save(migrated);
  assert.equal((await new LocalRepository(storage).load()).groups[1]!.members[0]!.name, '직접 수정');
});
