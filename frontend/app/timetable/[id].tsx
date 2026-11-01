import React, { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Button, Chip, Empty, Screen, T } from '../../src/components/ui';
import { TimetableGrid } from '../../src/components/TimetableGrid';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
export default function Timetable() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { data, update } = useApp(); const { colors: c } = useTheme();
  const group = data?.groups.find(g => g.id === id); const [memberId, setMemberId] = useState(group?.members[0]?.id);
  const member = group?.members.find(m => m.id === memberId) ?? group?.members[0];
  if (!group || !member) return <Screen back title="시간표"><Empty title="모임이 없어요" description="홈에서 모임을 먼저 만들어 주세요."/></Screen>;
  return <Screen back title="우리의 일주일" eyebrow="WEEKLY TIMETABLE"><T muted>수업이 있는 칸을 눌러 채워 주세요.{'\n'}매주 반복되는 학기 시간표입니다.</T>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>{group.members.map(m => <Chip key={m.id} label={m.name || '팀원'} selected={m.id === member.id} onPress={() => setMemberId(m.id)}/>)}</ScrollView>
    <View style={{ gap: 18 }}><T size={13} bold>{member.name || '팀원'}의 시간표 <T size={12} muted>· {member.busy.length}개 수업 블록</T></T>
      <TimetableGrid cell={key => ({ label: member.busy.includes(key) ? '수업' : '공강', background: member.busy.includes(key) ? c.soft : c.surface, textColor: member.busy.includes(key) ? c.primary : c.muted, selected: member.busy.includes(key), description: member.busy.includes(key) ? '수업 있음, 누르면 공강' : '공강, 누르면 수업 있음' })} onPress={key => update(d => ({ ...d, groups: d.groups.map(g => g.id === id ? { ...g, updatedAt: new Date().toISOString(), members: g.members.map(m => m.id === member.id ? { ...m, busy: m.busy.includes(key) ? m.busy.filter(k => k !== key) : [...m.busy, key] } : m) } : g) }))}/>
    </View><T size={12} muted>버건디 칸은 수업, 빈 칸은 공강입니다. 1–6교시는 각각 90분이며 기기에 자동 저장돼요.</T>
    <Button onPress={() => router.push({ pathname: '/availability/[id]', params: { id } })}>공통 공강 확인하기</Button>
  </Screen>;
}
