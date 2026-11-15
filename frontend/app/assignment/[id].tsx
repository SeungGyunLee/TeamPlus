import React, { useCallback, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { api } from '../../src/data/api';
import { DataSource, RequestFeedback } from '../../src/components/ApiUi';
import { Badge, Button, Card, Empty, Field, Screen, Section, T } from '../../src/components/ui';
import { isIsoDate, kstDateAt, recommendationRangeError } from '../../src/domain/apiDates';
import { useResource, useTask } from '../../src/state/apiHooks';

export default function AssignmentDetail() {
  const { id, assignmentId } = useLocalSearchParams<{ id: string; assignmentId: string }>();
  const numericId = Number(assignmentId);
  const resource = useResource(useCallback(signal => Number.isSafeInteger(numericId) && numericId > 0 ? api?.assignment(id, numericId, signal) : undefined, [id, numericId]));
  const task = useTask();
  const [deadline, setDeadline] = useState<string>();
  if (resource.loading || resource.error) return <Screen back title="회의 단계"><RequestFeedback loading={resource.loading} error={resource.error} retry={resource.reload}/></Screen>;
  const assignment = resource.value;
  if (!assignment || !api) return <Screen back title="회의 단계"><Empty title="과제 정보를 찾을 수 없어요" description="과제 목록에서 다시 선택해 주세요."/></Screen>;
  const server = api;
  const currentDeadline = deadline ?? assignment.finalDeadline ?? '';
  const validDeadline = isIsoDate(currentDeadline) && currentDeadline >= kstDateAt();
  const source = assignment.deadlineSource === 'ai' ? 'AI 추출' : assignment.deadlineSource === 'user' ? '사용자 확인' : '미확인';

  function saveDeadline() {
    if (!validDeadline) return;
    void task.run(async () => {
      await server.updateDeadline(id, numericId, currentDeadline);
      setDeadline(undefined);
      resource.reload();
    });
  }

  return <Screen back title={assignment.title?.trim() || '회의 단계'}>
    <DataSource/>
    <Card>
      <T bold>최종 마감일 · {assignment.finalDeadline ?? '미확인'}</T>
      <T muted>출처 · {source}</T>
      {assignment.deadlineStatus !== 'ok' || assignment.deadlineSource === 'ai'
        ? <T>공지 원문과 마감일을 확인한 뒤 저장해 주세요.</T> : null}
      <Field value={currentDeadline} onChangeText={setDeadline} placeholder="YYYY-MM-DD" accessibilityLabel="최종 마감일"
        maxLength={10} editable={!task.busy} autoCorrect={false}/>
      {!validDeadline && currentDeadline.length > 0 && <T muted>한국 시간 기준 오늘 이후 날짜를 YYYY-MM-DD로 입력해 주세요.</T>}
      <RequestFeedback loading={task.busy} error={task.error}/>
      <Button disabled={task.busy || !validDeadline} onPress={saveDeadline}>{task.error ? '저장 다시 시도' : '마감일 확인·저장'}</Button>
    </Card>
    {!!assignment.milestones.length && <>
      <Section title="중간 일정"/>
      <Card>{assignment.milestones.map((milestone, index) => <T key={index}>{milestone.name} · {milestone.date ?? '날짜 미정'}</T>)}</Card>
    </>}
    <Section title="회의 단계"/>
    {!assignment.stages.length && <Empty title="회의 단계가 없어요" description="과제 공지를 확인해 주세요."/>}
    {assignment.stages.map(stage => {
      const from = stage.windowStart ?? '';
      const to = stage.windowEnd ?? '';
      const rangeError = stage.dropped || !from || !to ? '추천할 날짜 범위가 없어요.' : recommendationRangeError(from, to);
      return <Card key={stage.position}>
        <Badge tone={stage.priority === 'must' ? 'primary' : 'muted'}>{stage.priority === 'must' ? '필수' : '선택'}</Badge>
        <T size={18} bold>{stage.name}</T><T>{stage.purpose}</T>
        <T muted>{from && to ? `${from} ~ ${to}` : '권장 날짜 미정'}</T>
        {stage.anchoredTo && <T muted size={12}>기준 일정 · {stage.anchoredTo}</T>}
        {rangeError ? <T muted size={13}>{rangeError}</T> : <Button variant="outline" onPress={() => router.push({
          pathname: '/recommend/[id]', params: { id, dateFrom: from, dateTo: to },
        })}>이 날짜로 장소 추천</Button>}
      </Card>;
    })}
  </Screen>;
}
