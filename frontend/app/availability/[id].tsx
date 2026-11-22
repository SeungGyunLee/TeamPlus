import React, { useCallback, useState } from 'react';
import { Pressable, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';
import { Badge, Button, Card, Chip, Empty, Row, Screen, Section, T } from '../../src/components/ui';
import { TimetableGrid } from '../../src/components/TimetableGrid';
import { api } from '../../src/data/api';
import type { AvailabilityBlock } from '../../src/data/api';
import { useGroup, useResource } from '../../src/state/apiHooks';
import { RequestFeedback } from '../../src/components/ApiUi';
import { useTheme } from '../../src/theme/theme';
import { rankedAvailability } from '../../src/domain/availability';
import { selectedAvailability, selectedParticipants } from '../../src/domain/collaboration';
import { DAYS, PERIODS, SlotKey } from '../../src/domain/model';
export default function Availability() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { colors: c } = useTheme();
  const groupResource = useGroup(id);
  const availability = useResource(useCallback(signal => api?.availability(id, signal), [id]));
  const [selected, setSelected] = useState<SlotKey | null>(null); const [showAll, setShowAll] = useState(false);
  const [simulation, setSimulation] = useState(false);
  const [excludedIds, setExcludedIds] = useState<string[]>([]);
  const { group } = groupResource;
  const failure = groupResource.error || availability.error;
  if (api && (failure || groupResource.loading || availability.loading)) return <Screen back title="공통 공강">
    <RequestFeedback loading={!failure && (groupResource.loading || availability.loading)} error={failure} retry={() => { groupResource.reload(); availability.reload(); }}/>
  </Screen>;
  if (!group) return <Screen back title="공통 공강"><Empty title="모임이 없어요" description="홈에서 모임을 선택해 주세요."/></Screen>;
  const blocks: AvailabilityBlock[] = api ? availability.value?.blocks ?? [] : rankedAvailability(group).map(block => ({
    key: block.key, day: block.day, period: block.period, periodLabel: PERIODS[block.period]!, count: block.count, total: block.total,
    level: block.count === block.total ? 'full' : block.count > 0 ? 'partial' : 'none',
    availableMemberIds: block.available.map(member => member.id), unavailableMemberIds: block.unavailable.map(member => member.id),
  }));
  const memberIds = group.members.map(member => member.id);
  const includedIds = selectedParticipants(memberIds, excludedIds);
  const projected = simulation ? selectedAvailability(blocks, includedIds) : blocks;
  const newlyFree = new Set(projected.filter(block => block.level === 'full' && blocks.find(original => original.key === block.key)?.level !== 'full').map(block => block.key));
  const ranked = projected.map(block => ({
    ...block,
    available: group.members.filter(member => block.availableMemberIds.includes(member.id)),
    unavailable: group.members.filter(member => block.unavailableMemberIds.includes(member.id)),
  }));
  const result = ranked.find(slot => slot.key === selected) ?? ranked[0];
  if (!result) return <Screen back title="공통 공강"><Empty title="공강 결과가 없어요" description="시간표를 확인한 뒤 다시 열어 주세요."/></Screen>;
  const full = ranked.filter(slot => slot.level === 'full').length;
  return <Screen back title="함께 비는 시간" eyebrow="FIND YOUR MOMENT"><Row style={{ justifyContent: 'space-between' }}><T muted style={{ flex: 1 }}>{group.name}</T><Badge>{simulation ? '선택한 ' + includedIds.length : group.members.length}명 기준</Badge></Row>
    <Row><Chip label="전체 팀원" selected={!simulation} onPress={() => setSimulation(false)}/><Chip label="참석자 선택" selected={simulation} onPress={() => setSimulation(true)}/></Row>
    {simulation && <Card><T bold>이번 회의 참석자</T><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {group.members.map(member => {
        const checked = includedIds.includes(member.id);
        const disabled = checked && includedIds.length === 1;
        return <Pressable key={member.id} accessibilityRole="checkbox" accessibilityLabel={member.name + ' 참석'}
          accessibilityState={{ checked, disabled }} disabled={disabled}
          onPress={() => setExcludedIds(current => {
            const selectedIds = selectedParticipants(memberIds, current);
            const next = selectedIds.includes(member.id) ? selectedIds.filter(id => id !== member.id) : [...selectedIds, member.id];
            return next.length ? memberIds.filter(id => !next.includes(id)) : current;
          })}
          style={{ minHeight: 44, paddingHorizontal: 14, justifyContent: 'center', borderRadius: 10, borderWidth: 1,
            borderColor: checked ? c.primary : c.border, backgroundColor: checked ? c.soft : c.surface }}>
          <T bold={checked}>{checked ? '✓ ' : ''}{member.name}</T>
        </Pressable>;
      })}
    </View><T size={12} muted>최소 1명을 선택해 주세요. 선택한 사람의 주간 공강을 미리 볼 수 있어요.</T>
      <Button size="sm" variant="ghost" onPress={() => setExcludedIds([])}>전원 선택</Button>
    </Card>}
    <Animated.View key={`${simulation}-${full}`} entering={FadeIn.duration(180).reduceMotion(ReduceMotion.System)}><Card>
      <Row style={{ alignItems: 'baseline' }}><T size={42} bold color={c.primary}>{full}</T><T bold>개 블록에서 {simulation ? '선택 인원' : '전원'} 참석 가능</T></Row>
      {simulation && <T color={c.success}>새로 함께 가능한 시간 +{newlyFree.size}칸</T>}
      <T size={12} muted>{simulation ? '＋ 표시는 전체 팀원 기준보다 새로 함께 가능한 시간이에요.' : '팀원 시간표가 변경되면 다시 조회해요.'}</T>
    </Card></Animated.View>
    <TimetableGrid cell={key => { const s = ranked.find(x => x.key === key); if (!s) return { label: '—', background: c.surface, textColor: c.muted, description: '데이터 없음' }; return { label: `${s.count}/${s.total}${newlyFree.has(key) ? '＋' : ''}`, background: newlyFree.has(key) ? c.successBg : s.level === 'full' ? c.soft : s.level === 'partial' ? c.successBg : c.occupied, textColor: s.level === 'full' ? c.primary : s.level === 'partial' ? c.success : c.muted, selected: result.key === key, description: `${s.total}명 중 ${s.count}명 참석 가능${newlyFree.has(key) ? ', 새로 함께 가능한 시간' : ''}` }; }} onPress={setSelected}/>
    <T size={12} muted>각 칸은 참석 가능 인원 / 전체 인원입니다. 칸을 누르면 팀원별 참석 여부를 볼 수 있어요.</T>
    <Animated.View key={`${result.key}-${group.members.length}-${result.count}`} entering={FadeIn.duration(150).reduceMotion(ReduceMotion.System)}><Card><Badge tone={result.count === result.total ? 'primary' : 'success'}>{result.count}명 참석 가능</Badge><T size={20} bold>{DAYS[result.day]}요일 {result.period + 1}교시</T><T muted>{PERIODS[result.period]}</T><View style={{ gap: 8 }}>{result.available.map(m => <Row key={m.id}><T color={c.success} size={13}>참석 가능</T><T bold>{m.name || '팀원'}</T></Row>)}{result.unavailable.map(m => <Row key={m.id}><T muted size={13}>수업 있음</T><T muted>{m.name || '팀원'}</T></Row>)}</View></Card></Animated.View>
    <Section title="참석하기 좋은 순서" extra="동률은 요일·교시순"/>
    <View style={{ gap: 8 }}>{ranked.slice(0, showAll ? 30 : 5).map(s => <Chip key={s.key} label={`${DAYS[s.day]} ${s.period + 1}교시 · ${PERIODS[s.period]} · ${s.count}/${s.total}명`} selected={s.key === result.key} onPress={() => setSelected(s.key)}/>)}</View><Button variant="outline" onPress={() => setShowAll(!showAll)}>{showAll ? '접기' : '30개 시간 모두 보기'}</Button>
    {api && <><T size={12} muted>장소 추천은 모임의 전체 팀원 시간표를 기준으로 해요.</T><Button onPress={() => router.push({ pathname: '/recommend/[id]', params: { id } })}>전체 팀원으로 장소 추천</Button></>}
  </Screen>;
}
