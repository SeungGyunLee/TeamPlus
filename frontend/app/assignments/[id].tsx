import React, { useCallback, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { api } from '../../src/data/api';
import { DataSource, RequestFeedback } from '../../src/components/ApiUi';
import { Button, Card, Empty, Field, LinkRow, Screen, Section, T } from '../../src/components/ui';
import { useGroup, useResource, useTask } from '../../src/state/apiHooks';

export default function Assignments() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const group = useGroup(id);
  const list = useResource(useCallback(signal => api?.assignments(id, signal), [id]));
  const task = useTask();
  const [title, setTitle] = useState('');
  const [notice, setNotice] = useState('');

  function analyze() {
    const server = api;
    if (!server || !notice.trim()) return;
    void task.run(async () => {
      const assignment = await server.createAssignment(id, title.trim(), notice.trim());
      setTitle('');
      setNotice('');
      router.push({ pathname: '/assignment/[id]', params: { id, assignmentId: String(assignment.id) } });
    });
  }

  return <Screen back title="과제 공지 분석">
    <DataSource/>
    {!api ? <Empty title="서버 연결이 필요해요" description="서버 주소를 설정한 후 과제 공지를 분석할 수 있어요."/>
      : group.loading || group.error ? <RequestFeedback loading={group.loading} error={group.error} retry={group.reload}/>
      : !group.group ? <Empty title="모임을 찾을 수 없어요" description="홈에서 모임을 다시 선택해 주세요."/>
      : <>
        <T muted>{group.group.name}</T>
        <Card>
          <Field value={title} onChangeText={setTitle} editable={!task.busy} placeholder="과제 제목 (선택)" accessibilityLabel="과제 제목" maxLength={200}/>
          <Field value={notice} onChangeText={setNotice} editable={!task.busy} placeholder="과제 공지 내용을 붙여 넣어 주세요" accessibilityLabel="과제 공지"
            multiline maxLength={5000} style={{ minHeight: 132, textAlignVertical: 'top' }}/>
          <RequestFeedback loading={task.busy} error={task.error}/>
          <Button disabled={task.busy || !notice.trim()} onPress={analyze}>{task.error ? '분석 다시 시도' : '공지 분석하기'}</Button>
        </Card>
        <Section title="분석한 과제"/>
        <RequestFeedback loading={list.loading} error={list.error} retry={list.reload}/>
        {list.value?.length === 0 && <Empty title="분석한 과제가 없어요" description="과제 공지를 입력하면 회의 단계를 확인할 수 있어요."/>}
        {list.value?.map(assignment => <LinkRow key={assignment.id} title={assignment.title?.trim() || '제목 없는 과제'} description={assignment.finalDeadline || '마감일 확인 필요'}
          onPress={() => router.push({ pathname: '/assignment/[id]', params: { id, assignmentId: String(assignment.id) } })}/>)}
      </>}
  </Screen>;
}
