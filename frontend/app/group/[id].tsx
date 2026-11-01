import React, { useState } from 'react';
import { View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Badge, Button, Card, Empty, Field, LinkRow, Row, Screen, Section, T } from '../../src/components/ui';
import { Confirm } from '../../src/components/Confirm';
import { useApp } from '../../src/state/AppProvider';
import { Group, uid } from '../../src/domain/model';
export default function GroupScreen() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { data, update } = useApp();
  const [remove, setRemove] = useState<string | null>(null); const [deleteGroup, setDeleteGroup] = useState(false);
  const group = data?.groups.find(g => g.id === id);
  if (!group) return <Screen back title="모임을 찾을 수 없어요"><Empty title="삭제된 모임이에요" description="홈에서 다른 모임을 선택해 주세요."/></Screen>;
  function change(fn: (g: Group) => Group) { update(d => ({ ...d, groups: d.groups.map(g => g.id === id ? { ...fn(g), updatedAt: new Date().toISOString() } : g) })); }
  return <Screen back title="모임 관리" eyebrow="YOUR TEAM">
    <View style={{ gap: 9 }}><T size={12} muted>모임 이름 · 자동 저장</T><Field accessibilityLabel="모임 이름" value={group.name} onChangeText={name => change(g => ({ ...g, name }))} placeholder="모임 이름을 입력하세요" onBlur={() => { if (!group.name.trim()) change(g => ({ ...g, name: '이름 없는 모임' })); }}/></View>
    <Section title="함께하는 사람들" extra={`${group.members.length}명`}/>
    <Card>{group.members.map((member, index) => <Row key={member.id}><Badge>{String(index + 1).padStart(2, '0')}</Badge><Field accessibilityLabel={`팀원 ${index + 1} 이름`} value={member.name} style={{ flex: 1 }} onChangeText={name => change(g => ({ ...g, members: g.members.map(m => m.id === member.id ? { ...m, name } : m) }))} placeholder="팀원 이름"/><Button variant="ghost" size="sm" disabled={group.members.length <= 1} accessibilityLabel={`${member.name} 삭제`} onPress={() => setRemove(member.id)}>삭제</Button></Row>)}
      <Button variant="outline" onPress={() => change(g => ({ ...g, members: [...g.members, { id: uid(), name: `팀원 ${g.members.length + 1}`, busy: [] }] }))}>팀원 추가</Button>
    </Card><T size={12} muted>지금은 모임을 만든 사람이 모든 팀원의 시간표를 입력해요. 변경한 내용은 기기에 자동 저장됩니다.</T>
    <LinkRow title="팀원별 시간표" description="월–금 · 90분 수업 블록" onPress={() => router.push({ pathname: '/timetable/[id]', params: { id } })}/>
    <LinkRow title="공통 공강 확인" description="참석 가능한 인원이 많은 시간부터" onPress={() => router.push({ pathname: '/availability/[id]', params: { id } })}/>
    <Button variant="ghost" onPress={() => setDeleteGroup(true)}>모임 삭제</Button>
    <Confirm visible={!!remove} title="팀원을 삭제할까요?" confirmLabel="팀원 삭제" onCancel={() => setRemove(null)} onConfirm={() => { change(g => ({ ...g, members: g.members.length > 1 ? g.members.filter(m => m.id !== remove) : g.members })); setRemove(null); }}><T muted>이 팀원의 시간표도 함께 삭제됩니다.</T></Confirm>
    <Confirm visible={deleteGroup} title="모임을 삭제할까요?" confirmLabel="모임 삭제" onCancel={() => setDeleteGroup(false)} onConfirm={() => { update(d => ({ ...d, groups: d.groups.filter(g => g.id !== id), reservations: d.reservations.map(r => r.groupId === id ? { ...r, status: 'cancelled' } : r) })); setDeleteGroup(false); router.replace('/'); }}><T muted>팀원과 시간표가 삭제되고 이 모임의 가상 예약은 취소됩니다.</T></Confirm>
  </Screen>;
}
