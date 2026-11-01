import React from 'react';
import { Pressable, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowUpRight, Plus, UsersRound } from 'lucide-react-native';
import { Badge, Button, Card, Empty, LinkRow, Row, Screen, Section, T } from '../../src/components/ui';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
import { rankedAvailability } from '../../src/domain/availability';
import { Group, NEW_GROUP_MEMBER_NAMES, uid } from '../../src/domain/model';
export default function Home() {
  const { data, update } = useApp(); const { colors: c } = useTheme();
  if (!data) return null;
  const recent = [...data.groups].sort((a,b) => b.updatedAt.localeCompare(a.updatedAt))[0];
  const full = recent ? rankedAvailability(recent).filter(s => s.count === s.total).length : 0;
  function create() {
    const id = uid();
    const group: Group = { id, name: '새로운 모임', ownerId: 'local-owner', inviteCode: null, updatedAt: new Date().toISOString(), members: NEW_GROUP_MEMBER_NAMES.map(name => ({ id: uid(), name, busy: [] })) };
    update(d => ({ ...d, groups: [group, ...d.groups] }));
    router.push({ pathname: '/group/[id]', params: { id } });
  }
  return <Screen title="KW Meet" eyebrow="CAMPUS, CONNECTED." action={<View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: c.soft, alignItems: 'center', justifyContent: 'center' }}><T size={13} bold color={c.primary}>KW</T></View>}>
    <View style={{ paddingTop: 10, gap: 8 }}><T size={33} bold style={{ lineHeight: 44, letterSpacing: -1.2 }}>함께할 시간,{'\n'}머물 공간.</T><T muted>우리의 다음 모임을 가볍게 시작하세요.</T></View>
    {recent && <Pressable accessibilityRole="button" accessibilityLabel="최근 모임 공통 공강 확인" onPress={() => router.push({ pathname: '/availability/[id]', params: { id: recent.id } })}><Card style={{ backgroundColor: c.primary, borderColor: c.primary, shadowColor: c.shadow, shadowOpacity: 0.14, shadowRadius: 15, shadowOffset: { width: 0, height: 7 }, elevation: 3, gap: 24 }}>
      <Row style={{ justifyContent: 'space-between' }}><T size={12} color={c.onPrimary} style={{ opacity: 0.85 }}>이번 주의 공통 공강</T><ArrowUpRight color={c.onPrimary} size={21}/></Row>
      <Row style={{ alignItems: 'baseline', gap: 6 }}><T size={56} bold color={c.onPrimary} style={{ lineHeight: 64 }}>{full}</T><T color={c.onPrimary}>개의 시간</T></Row>
      <Row style={{ justifyContent: 'space-between' }}><T size={13} color={c.onPrimary} style={{ flex: 1 }} numberOfLines={1}>{recent.name}</T><T size={12} color={c.onPrimary}>{recent.members.length}명 모두 함께</T></Row>
    </Card></Pressable>}
    <Section title="나의 모임" extra={`${data.groups.length}개 모임`}/>
    {data.groups.length === 0 && <Empty title="첫 모임을 만들어 보세요" description="팀원 3명으로 시작해 인원과 이름을 자유롭게 바꿀 수 있어요."/>}
    <View style={{ gap: 12 }}>{data.groups.map((g, i) => <Pressable key={g.id} accessibilityRole="button" accessibilityLabel={`${g.name} 관리`} onPress={() => router.push({ pathname: '/group/[id]', params: { id: g.id } })}><Card><Row style={{ justifyContent: 'space-between' }}><Badge>{String(i + 1).padStart(2, '0')} · 모임</Badge><ArrowUpRight size={18} color={c.muted}/></Row><T size={20} bold>{g.name || '이름 없는 모임'}</T><Row><UsersRound color={c.muted} size={15}/><T size={12} muted style={{ flex: 1 }} numberOfLines={1}>{g.members.map(m => m.name || '팀원').join(' · ')}</T><T size={12} bold>{g.members.length}명</T></Row></Card></Pressable>)}</View>
    <Button variant="outline" onPress={create}><Row><Plus size={18} color={c.primary}/><T color={c.primary} bold>새 모임 만들기</T></Row></Button>
    <Section title="모임에 어울리는 공간"/><LinkRow title="캠퍼스 공간 둘러보기" description="집현전부터 조용한 라운지까지" arrow onPress={() => router.push('/places')}/>
    <T size={11} muted style={{ letterSpacing: 1 }}>KW MEET · YOUR CAMPUS WORKSPACE</T>
  </Screen>;
}
