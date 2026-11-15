import React, { useState } from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import { api } from '../data/api';
import { useGroup, useTask } from '../state/apiHooks';
import { Confirm } from './Confirm';
import { RequestFeedback } from './ApiUi';
import { Badge, Button, Card, Empty, Field, LinkRow, Row, Screen, Section, T } from './ui';

function NameField({ name, label, maxLength, disabled, save }: {
  name: string; label: string; maxLength: number; disabled: boolean; save: (name: string) => void;
}) {
  const [draft, setDraft] = useState(name);
  return <Field style={{ flex: 1 }} value={draft} onChangeText={setDraft} accessibilityLabel={label}
    maxLength={maxLength} editable={!disabled} returnKeyType="done"
    onEndEditing={({ nativeEvent }) => {
      const value = nativeEvent.text.trim() || (label === '모임 이름' ? '이름 없는 모임' : '');
      if (value !== name) save(value);
      else setDraft(name);
    }}/>;
}

export function ServerGroup({ id }: { id: string }) {
  const { group, loading, error, reload } = useGroup(id);
  const task = useTask();
  const [confirm, setConfirm] = useState<{ id: string; name: string } | 'group'>();
  const [retryEdit, setRetryEdit] = useState<(() => void)>();
  function mutate(action: () => Promise<unknown>, retryable = false) {
    const perform = () => {
      void task.run(async () => {
        setRetryEdit(retryable ? () => perform : undefined);
        await action();
        setConfirm(undefined);
        setRetryEdit(undefined);
        reload();
      });
    };
    perform();
  }

  if (loading || error) return <Screen back title="모임 관리"><RequestFeedback loading={loading} error={error} retry={reload}/></Screen>;
  if (!group || !api) return <Screen back title="모임 관리"><Empty title="모임을 찾을 수 없어요" description="홈에서 다시 선택해 주세요."/></Screen>;
  const server = api;
  const target = confirm;
  return <Screen back title="모임 관리" eyebrow="YOUR TEAM">
    <View style={{ gap: 9 }}><T size={12} muted>모임 이름 · 입력 후 서버에 저장</T>
      <NameField key={group.name} name={group.name} label="모임 이름" maxLength={100} disabled={task.busy} save={name => mutate(() => server.renameGroup(id, name), true)}/>
    </View>
    <Section title="함께하는 사람들" extra={group.members.length + '명'}/>
    <Card>
      {group.members.map((member, index) => <Row key={member.id}>
        <Badge>{String(index + 1).padStart(2, '0')}</Badge>
        <NameField key={member.name} name={member.name} label={`팀원 ${index + 1} 이름`} maxLength={50} disabled={task.busy} save={name => mutate(() => server.updateMember(id, member.id, { name }), true)}/>
        <Button variant="ghost" size="sm" disabled={task.busy || group.members.length <= 1} onPress={() => setConfirm(member)} accessibilityLabel={member.name + ' 삭제'}>삭제</Button>
      </Row>)}
      <Button variant="outline" disabled={task.busy || group.members.length >= 12} onPress={() => mutate(() => server.addMember(id, '팀원 ' + (group.members.length + 1)))}>팀원 추가</Button>
      <T muted size={12}>모임은 최대 12명까지 함께할 수 있어요.</T>
    </Card>
    <RequestFeedback loading={task.busy} error={task.error} retry={retryEdit}/>
    <LinkRow title="팀원별 시간표" description="월–금 · 90분 수업 블록" onPress={() => router.push({ pathname: '/timetable/[id]', params: { id } })}/>
    <LinkRow title="공통 공강 확인" description="참석 가능한 인원이 많은 시간부터" onPress={() => router.push({ pathname: '/availability/[id]', params: { id } })}/>
    <LinkRow title="조건으로 장소 추천" description="자연어로 조건을 입력해요" onPress={() => router.push({ pathname: '/recommend/[id]', params: { id } })}/>
    <LinkRow title="과제 공지 분석" description="회의 단계와 권장 날짜를 확인해요" onPress={() => router.push({ pathname: '/assignments/[id]', params: { id } })}/>
    <Button variant="ghost" disabled={task.busy} onPress={() => setConfirm('group')}>모임 삭제</Button>
    <Confirm visible={!!target} title={target === 'group' ? '모임을 삭제할까요?' : '팀원을 삭제할까요?'}
      confirmLabel={target === 'group' ? '모임 삭제' : '팀원 삭제'} onCancel={() => setConfirm(undefined)}
      onConfirm={() => {
        setConfirm(undefined);
        if (target === 'group') void task.run(async () => { await server.deleteGroup(id); router.replace('/'); });
        else if (target) mutate(() => server.deleteMember(id, target.id));
      }}>
      <T muted>{target === 'group' ? '모임, 팀원, 시간표와 과제 정보가 삭제됩니다.' : '팀원의 시간표도 함께 삭제됩니다.'}</T>
    </Confirm>
  </Screen>;
}
