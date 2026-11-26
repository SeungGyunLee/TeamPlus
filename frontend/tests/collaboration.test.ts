import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { Assignment, AvailabilityBlock, Candidate } from '../src/data/api';
import { initialData } from '../src/data/seed';
import { rankedAvailability } from '../src/domain/availability';
import { selectedAvailability, selectedParticipants, stageKey, timelineSummary, meetingShareDraft, projectShareDraft, shareMessage, ProjectProgress } from '../src/domain/collaboration';
import { decodeProgress, ProgressRepository, progressStorageKey } from '../src/data/progressRepository';

const group = initialData().groups[0]!;
const blocks: AvailabilityBlock[] = rankedAvailability(group).map(block => ({
  key: block.key, day: block.day, period: block.period, periodLabel: '', count: block.count, total: block.total,
  level: block.count === block.total ? 'full' : block.count > 0 ? 'partial' : 'none',
  availableMemberIds: block.available.map(member => member.id), unavailableMemberIds: block.unavailable.map(member => member.id),
}));
const assignment: Assignment = {
  id: 10, title: '팀 프로젝트', finalDeadline: '2030-01-15', deadlineSource: 'user', deadlineStatus: 'ok',
  deliverableType: 'presentation', milestones: [], stages: [
    { position: 0, name: '주제 선정', purpose: '주제 합의', priority: 'must', windowStart: '2030-01-08', windowEnd: '2030-01-09', anchoredTo: null, dropped: false },
    { position: 1, name: '발표 연습', purpose: '발표 확인', priority: 'optional', windowStart: null, windowEnd: null, anchoredTo: null, dropped: true },
  ],
};
const empty: ProjectProgress = { version: 1, stages: {} };

test('removing the only selected teammate restores a valid selection among remaining members', () => {
  assert.deepEqual(selectedParticipants(['a', 'b', 'c'], ['b', 'c']), ['a']);
  assert.deepEqual(selectedParticipants(['b', 'c'], ['b', 'c']), ['b', 'c']);
  assert.deepEqual(selectedParticipants(['b', 'c'], ['gone', 'c']), ['b']);
});

test('selected participants intersect server blocks without mutating group or server response', () => {
  const before = JSON.stringify({ group, blocks });
  const last = group.members[2]!.id;
  const result = selectedAvailability(blocks, [last, last]);
  assert.equal(result.length, 30);
  const monday = result.find(block => block.key === '0-0')!;
  assert.equal(monday.total, 1);
  assert.equal(monday.count, 1);
  assert.equal(monday.level, 'full');
  assert.deepEqual(monday.availableMemberIds, [last]);
  assert.equal(JSON.stringify({ group, blocks }), before);
  assert.ok(result.every(block => block.count + block.unavailableMemberIds.length === block.total));
  assert.ok(selectedAvailability(blocks, []).every(block => block.level === 'none'));
});

test('restoring all participants preserves original counts and stable weekday ordering', () => {
  const restored = selectedAvailability(blocks, group.members.map(member => member.id));
  for (const block of blocks) {
    assert.equal(restored.find(item => item.key === block.key)!.count, block.count);
  }
  for (let i = 1; i < restored.length; i++) {
    const previous = restored[i - 1]!;
    const current = restored[i]!;
    assert.ok(previous.count > current.count || previous.count === current.count &&
      (previous.day < current.day || previous.day === current.day && previous.period < current.period));
  }
});

test('timeline excludes dropped stages and preserves progress through deadline replanning', () => {
  const stage = assignment.stages[0]!;
  const progress: ProjectProgress = { version: 1, stages: { [stageKey(stage)]: { completed: true, note: '노트북' } } };
  const changed = { ...assignment, finalDeadline: '2030-01-20', stages: [{ ...stage, windowStart: '2030-01-12', windowEnd: '2030-01-14' }, assignment.stages[1]!] };
  assert.equal(stageKey(stage), stageKey(changed.stages[0]!));
  const summary = timelineSummary(changed, progress, '2030-01-10');
  assert.equal(summary.daysLeft, 10);
  assert.equal(summary.total, 1);
  assert.equal(summary.completed, 1);
  assert.equal(summary.percent, 100);
  assert.equal(summary.next, undefined);
  assert.notEqual(stageKey(stage), stageKey({ ...stage, name: '다른 단계' }));
});

test('timeline handles missing deadlines, past deadlines and no stages', () => {
  assert.equal(timelineSummary({ ...assignment, finalDeadline: null }, empty).daysLeft, null);
  assert.equal(timelineSummary(assignment, empty, '2030-01-16').daysLeft, -1);
  assert.equal(timelineSummary(assignment, empty, '2030-01-15').daysLeft, 0);
  const summary = timelineSummary({ ...assignment, stages: [] }, empty);
  assert.equal(summary.percent, 0);
  assert.equal(summary.total, 0);
});

class MemoryStorage {
  values = new Map<string, string>();
  fail = false;
  async getItem(key: string) { return this.values.get(key) ?? null; }
  async setItem(key: string, value: string) {
    await new Promise(resolve => setTimeout(resolve, 2));
    if (this.fail) throw new Error('disk full');
    this.values.set(key, value);
  }
}

test('progress remains isolated across server, group and assignment and restores after restart', async () => {
  const storage = new MemoryStorage();
  const repository = new ProgressRepository(storage);
  const key = progressStorageKey('https://example.test/', 'group', 1);
  assert.equal(key, progressStorageKey('https://example.test', 'group', 1));
  const value: ProjectProgress = { version: 1, stages: { test: { completed: true, note: '자료' } } };
  await repository.save(key, value);
  assert.deepEqual(await new ProgressRepository(storage).load(key), value);
  for (const other of [progressStorageKey('device', 'group', 1), progressStorageKey('https://example.test', 'other', 1), progressStorageKey('https://example.test', 'group', 2)]) {
    assert.deepEqual(await repository.load(other), empty);
  }
});

test('rapid progress writes retain newest snapshot and recover after failed saves', async () => {
  const storage = new MemoryStorage();
  const repository = new ProgressRepository(storage);
  const value = (note: string): ProjectProgress => ({ version: 1, stages: { test: { completed: true, note } } });
  await Promise.all([repository.save('key', value('a')), repository.save('key', value('ab')), repository.save('key', value('abc'))]);
  assert.deepEqual(await repository.load('key'), value('abc'));
  storage.fail = true;
  await assert.rejects(repository.save('key', value('failed')));
  storage.fail = false;
  await repository.save('key', value('retried'));
  assert.deepEqual(await repository.load('key'), value('retried'));
});

test('invalid progress is reported while its original bytes remain untouched', async () => {
  const storage = new MemoryStorage();
  storage.values.set('key', '{broken');
  await assert.rejects(new ProgressRepository(storage).load('key'));
  assert.equal(storage.values.get('key'), '{broken');
  assert.throws(() => decodeProgress('{"version":1,"stages":[]}'));
  assert.throws(() => decodeProgress('{"version":1,"stages":{"a":{"completed":"yes","note":""}}}'));
});

test('meeting message carries stage context, attendee names and edited preview without confirming booking', () => {
  const candidate: Candidate = {
    candidateId: 'test', date: '2030-01-10', hour: 11, label: '11:00–12:00', score: 100, status: 'green',
    availableMemberIds: [group.members[0]!.id], unavailableMemberIds: [group.members[1]!.id], conditionsMet: [], conflicts: [], reason: null,
    room: { id: 'J201', name: '201호', fullName: '집현전 201호', placeId: 'library', capacity: 4, hasOutlet: true, noiseLevel: 'quiet', laptopSpace: true },
  };
  const draft = meetingShareDraft(candidate, group, { assignmentTitle: '과제', stageName: '주제 선정', purpose: '주제 합의', preparation: '노트북' });
  const message = shareMessage({ ...draft, title: '수정한 제목', preparation: '충전기' });
  for (const value of ['수정한 제목', '2030-01-10 11:00–12:00 (한국 시간)', '집현전 201호', group.members[0]!.name, '주제 선정', '주제 합의', '충전기', '예약 여부는 별도로 확인']) assert.ok(message.includes(value), value);
  assert.ok(!message.includes('노트북'));
  assert.equal(meetingShareDraft(candidate, group).purpose, '');
});

test('project share contains only active stages, accurate progress and personal-device scope', () => {
  const progress: ProjectProgress = { version: 1, stages: { [stageKey(assignment.stages[0]!)]: { completed: true, note: '노트북' } } };
  const message = shareMessage(projectShareDraft(assignment, progress));
  for (const text of ['팀 프로젝트', '2030-01-15', '1/1단계 (100%)', '노트북', '이 기기에 기록']) assert.ok(message.includes(text));
  assert.ok(!message.includes('발표 연습'));
});
