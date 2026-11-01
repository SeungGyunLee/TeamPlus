import React, { useState } from 'react';
import { View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';
import { Badge, Button, Card, Chip, Empty, Row, Screen, Section, T } from '../../src/components/ui';
import { TimetableGrid } from '../../src/components/TimetableGrid';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
import { rankedAvailability } from '../../src/domain/availability';
import { DAYS, PERIODS, SlotKey } from '../../src/domain/model';
export default function Availability() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { data } = useApp(); const { colors: c } = useTheme();
  const [selected, setSelected] = useState<SlotKey | null>(null); const [showAll, setShowAll] = useState(false);
  const group = data?.groups.find(g => g.id === id);
  if (!group) return <Screen back title="공통 공강"><Empty title="모임이 없어요" description="홈에서 모임을 선택해 주세요."/></Screen>;
  const ranked = rankedAvailability(group); const result = ranked.find(s => s.key === selected) ?? ranked[0]!;
  const full = ranked.filter(s => s.count === s.total).length;
  return <Screen back title="함께 비는 시간" eyebrow="FIND YOUR MOMENT"><Row style={{ justifyContent: 'space-between' }}><T muted style={{ flex: 1 }}>{group.name}</T><Badge>{group.members.length}명 기준</Badge></Row>
    <Card><Row style={{ alignItems: 'baseline' }}><T size={42} bold color={c.primary}>{full}</T><T bold>개 블록에서 전원 참석 가능</T></Row><T size={12} muted>인원이 변경되면 결과도 바로 갱신됩니다.</T></Card>
    <TimetableGrid cell={key => { const s = ranked.find(x => x.key === key)!; return { label: `${s.count}/${s.total}`, background: s.count === s.total ? c.soft : s.count > 0 ? c.successBg : c.occupied, textColor: s.count === s.total ? c.primary : s.count > 0 ? c.success : c.muted, selected: result.key === key, description: `${s.total}명 중 ${s.count}명 참석 가능` }; }} onPress={setSelected}/>
    <T size={12} muted>각 칸은 참석 가능 인원 / 전체 인원입니다. 칸을 누르면 팀원별 참석 여부를 볼 수 있어요.</T>
    <Animated.View key={`${result.key}-${group.members.length}-${result.count}`} entering={FadeIn.duration(150).reduceMotion(ReduceMotion.System)}><Card><Badge tone={result.count === result.total ? 'primary' : 'success'}>{result.count}명 참석 가능</Badge><T size={20} bold>{DAYS[result.day]}요일 {result.period + 1}교시</T><T muted>{PERIODS[result.period]}</T><View style={{ gap: 8 }}>{result.available.map(m => <Row key={m.id}><T color={c.success} size={13}>참석 가능</T><T bold>{m.name || '팀원'}</T></Row>)}{result.unavailable.map(m => <Row key={m.id}><T muted size={13}>수업 있음</T><T muted>{m.name || '팀원'}</T></Row>)}</View></Card></Animated.View>
    <Section title="참석하기 좋은 순서" extra="동률은 요일·교시순"/>
    <View style={{ gap: 8 }}>{ranked.slice(0, showAll ? 30 : 5).map(s => <Chip key={s.key} label={`${DAYS[s.day]} ${s.period + 1}교시 · ${PERIODS[s.period]} · ${s.count}/${s.total}명`} selected={s.key === result.key} onPress={() => setSelected(s.key)}/>)}</View><Button variant="outline" onPress={() => setShowAll(!showAll)}>{showAll ? '접기' : '30개 시간 모두 보기'}</Button>
  </Screen>;
}
