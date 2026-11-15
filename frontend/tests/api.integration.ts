import assert from 'node:assert/strict';
import { ApiError, createApi } from '../src/data/api';
import { calendarTimes, isIsoDate, kstDateAt, recommendationRangeError } from '../src/domain/apiDates';
import { NEW_GROUP_MEMBER_NAMES } from '../src/domain/model';

async function run() {
  const server = createApi(process.env.TEAMPLUS_TEST_URL ?? 'http://127.0.0.1:8000');
  const noAi = createApi(process.env.TEAMPLUS_NO_AI_URL ?? 'http://127.0.0.1:8001');
  const group = await server.createGroup('프론트 API 검증', NEW_GROUP_MEMBER_NAMES);
  try {
    assert.ok((await server.groups()).some(item => item.id === group.id));
    assert.deepEqual(group.members.map(member => member.name), NEW_GROUP_MEMBER_NAMES);
    assert.equal((await server.renameGroup(group.id, 'API 검증 모임')).name, 'API 검증 모임');
    const member = await server.addMember(group.id, '검증 팀원');
    await server.updateMember(group.id, member.id, { name: '수정 팀원', busy: ['0-0'] });
    const saved = (await server.group(group.id)).members.find(item => item.id === member.id);
    assert.equal(saved?.name, '수정 팀원');
    assert.deepEqual(saved?.busy, ['0-0']);
    const availability = await server.availability(group.id);
    assert.equal(availability.blocks.length, 30);
    assert.equal(availability.fullCount, 29);
    assert.deepEqual(availability.blocks.find(slot => slot.key === '0-0')?.unavailableMemberIds, [member.id]);
    await server.deleteMember(group.id, member.id);
    assert.equal((await server.group(group.id)).members.length, 3);

    const places = await server.places();
    const list = await server.rooms();
    assert.ok(list.length > 0);
    const place = places.find(value => value.id === list[0]!.placeId);
    assert.equal((await server.place(place!.id)).id, place!.id);
    const from = kstDateAt(1);
    const to = kstDateAt(7);
    assert.ok((await server.roomAvailability(from, group.id)).every(room => room.slots.length === 10));
    assert.equal((await server.conditions(group.id, '[확인 질문] 조용한 공간')).type, 'question');
    const response = await server.conditions(group.id, '[확인 질문] 조용한 공간\n답변: 3명');
    assert.equal(response.type, 'conditions');
    const recommendations = await server.recommendations(group.id, response.conditions, from, to);
    assert.ok(recommendations.candidates.length > 0);
    assert.ok(recommendations.candidates.every(item => item.score >= 0 && item.score <= 100 && item.reason));
    const empty = await server.recommendations(group.id, { ...response.conditions, capacity: 100 }, from, to);
    assert.deepEqual(empty.candidates, []);
    await assert.rejects(server.recommendations(group.id, response.conditions, to, from),
      (error: unknown) => error instanceof ApiError && error.status === 422);
    const assignment = await server.createAssignment(group.id, '발표 준비', '중간 점검 후 발표를 준비하세요.');
    assert.ok((await server.assignments(group.id)).some(item => item.id === assignment.id));
    assert.equal((await server.assignment(group.id, assignment.id)).stages.length, 3);
    const updated = await server.updateDeadline(group.id, assignment.id, kstDateAt(15));
    assert.equal(updated.deadlineSource, 'user');
    assert.ok(updated.stages.some(stage => stage.windowStart && stage.windowEnd));
    console.log('PASS: group CRUD, member/timetable, availability, places/rooms, question+answer, recommendation/empty/422, assignment/deadline');
  } finally {
    await server.deleteGroup(group.id);
  }
  await assert.rejects(server.group(group.id), (error: unknown) => error instanceof ApiError && error.status === 404);
  const unavailable = await noAi.createGroup('Claude 미설정 검증', NEW_GROUP_MEMBER_NAMES);
  try {
    await assert.rejects(noAi.conditions(unavailable.id, '조용한 장소'),
      (error: unknown) => error instanceof ApiError && error.status === 503);
  } finally {
    await noAi.deleteGroup(unavailable.id);
  }
  await assert.rejects(createApi('http://127.0.0.1:1').groups(),
    (error: unknown) => error instanceof ApiError && error.message.includes('서버에 연결할 수 없어요'));
  const now = new Date('2026-11-13T15:05:00Z');
  assert.equal(kstDateAt(0, now), '2026-11-14');
  assert.equal(recommendationRangeError(kstDateAt(0, now), kstDateAt(29, now), now), null);
  assert.ok(recommendationRangeError(kstDateAt(0, now), kstDateAt(30, now), now));
  assert.equal(isIsoDate('2026-02-30'), false);
  assert.equal(new Date(calendarTimes('2026-11-14', 18)!.start).toISOString(), '2026-11-14T09:00:00.000Z');
  console.log('PASS: delete/404, Claude unavailable/503, network error, KST boundary and calendar timestamps');
}

void run().catch(error => { console.error(error); process.exitCode = 1; });
