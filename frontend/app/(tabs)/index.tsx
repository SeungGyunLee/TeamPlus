import React, { useCallback } from 'react';
import { Pressable, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowUpRight, Plus, UsersRound } from 'lucide-react-native';
import { Badge, Button, Card, Empty, LinkRow, Row, Screen, Section, T } from '../../src/components/ui';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
import { rankedAvailability } from '../../src/domain/availability';
import { Group, NEW_GROUP_MEMBER_NAMES, uid } from '../../src/domain/model';
import { api } from '../../src/data/api';
import { DataSource, RequestFeedback } from '../../src/components/ApiUi';
import { useResource, useTask } from '../../src/state/apiHooks';

export default function Home() {
  const { data, update } = useApp(); const { colors: c } = useTheme();
  const list = useResource(useCallback(signal => api?.groups(signal), []));
  const task = useTask();
  const groups = api ? list.value ?? [] : data?.groups ?? [];
  const recent = groups.reduce<Group | undefined>((latest, group) =>
    !latest || group.updatedAt > latest.updatedAt ? group : latest, undefined);
  function create() {
    const server = api;
    if (server) {
      void task.run(async () => {
        const group = await server.createGroup('새로운 모임', NEW_GROUP_MEMBER_NAMES);
        router.push({ pathname: '/group/[id]', params: { id: group.id } });
      });
      return;
    }
    const id = uid();
    const group: Group = { id, name: '새로운 모임', ownerId: 'local-owner', inviteCode: null, updatedAt: new Date().toISOString(), members: NEW_GROUP_MEMBER_NAMES.map(name => ({ id: uid(), name, busy: [] })) };
    update(d => ({ ...d, groups: [group, ...d.groups] }));
    router.push({ pathname: '/group/[id]', params: { id } });
  }
  return <Screen title="KW Meet" eyebrow="CAMPUS, CONNECTED." action={<View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: c.soft, alignItems: 'center', justifyContent: 'center' }}><T size={13} bold color={c.primary}>KW</T></View>}>
    <View style={{ paddingTop: 10, gap: 8 }}><T size={33} bold style={{ lineHeight: 44, letterSpacing: -1.2 }}>함께할 시간,{'\n'}머물 공간.</T><T muted>우리의 다음 모임을 가볍게 시작하세요.</T></View>
    <DataSource/>
    {api && <RequestFeedback loading={list.loading} error={list.error} retry={list.reload}/>}
    <RequestFeedback error={task.error}/>
    {recent && <Pressable accessibilityRole="button" accessibilityLabel="최근 모임 공통 공강 확인" onPress={() => router.push({ pathname: '/availability/[id]', params: { id: recent.id } })}><Card style={{ backgroundColor: c.primary, borderColor: c.primary, shadowColor: c.shadow, shadowOpacity: 0.14, shadowRadius: 15, shadowOffset: { width: 0, height: 7 }, elevation: 3, gap: 24 }}>
      <Row style={{ justifyContent: 'space-between' }}><T size={12} color={c.onPrimary} style={{ opacity: 0.85 }}>이번 주의 공통 공강</T><ArrowUpRight color={c.onPrimary} size={21}/></Row>
      <RecentFreeCount key={recent.id} group={recent}/>
      <Row style={{ justifyContent: 'space-between' }}><T size={13} color={c.onPrimary} style={{ flex: 1 }} numberOfLines={1}>{recent.name}</T><T size={12} color={c.onPrimary}>{recent.members.length}명 모두 함께</T></Row>
    </Card></Pressable>}
    <Section title="나의 모임" extra={`${groups.length}개 모임`}/>
    {groups.length === 0 && (!api || !!list.value) && <Empty title="첫 모임을 만들어 보세요" description="팀원 3명으로 시작해 인원과 이름을 자유롭게 바꿀 수 있어요."/>}
    <View style={{ gap: 12 }}>{groups.map((g, i) => <Pressable key={g.id} accessibilityRole="button" accessibilityLabel={`${g.name} 관리`} onPress={() => router.push({ pathname: '/group/[id]', params: { id: g.id } })}><Card><Row style={{ justifyContent: 'space-between' }}><Badge>{String(i + 1).padStart(2, '0')} · 모임</Badge><ArrowUpRight size={18} color={c.muted}/></Row><T size={20} bold>{g.name || '이름 없는 모임'}</T><Row><UsersRound color={c.muted} size={15}/><T size={12} muted style={{ flex: 1 }} numberOfLines={1}>{g.members.map(m => m.name || '팀원').join(' · ')}</T><T size={12} bold>{g.members.length}명</T></Row></Card></Pressable>)}</View>
    <Button variant="outline" disabled={task.busy} onPress={create}><Row><Plus size={18} color={c.primary}/><T color={c.primary} bold>새 모임 만들기</T></Row></Button>
    {api && recent && <LinkRow title="조건으로 장소 추천" description="모임 시간표와 조건을 함께 확인해요" onPress={() => router.push({ pathname: '/recommend/[id]', params: { id: recent.id } })}/>}
    <Section title="모임에 어울리는 공간"/><LinkRow title="캠퍼스 공간 둘러보기" description="집현전부터 조용한 라운지까지" arrow onPress={() => router.push('/places')}/>
    <T size={11} muted style={{ letterSpacing: 1 }}>KW MEET · YOUR CAMPUS WORKSPACE</T>
  </Screen>;
}

function RecentFreeCount({ group }: { group: Group }) {
  const { id } = group;
  const { colors: c } = useTheme();
  const availability = useResource(useCallback(signal => api?.availability(id, signal), [id]));
  const full = api ? availability.value?.fullCount
    : rankedAvailability(group).filter(slot => slot.count === slot.total).length;
  return <Row style={{ alignItems: 'baseline', gap: 6 }}>
    <T size={56} bold color={c.onPrimary} style={{ lineHeight: 64 }}>{full ?? '—'}</T>
    <T color={c.onPrimary}>{availability.error ? '공강 조회 실패' : '개의 시간'}</T>
  </Row>;
}
