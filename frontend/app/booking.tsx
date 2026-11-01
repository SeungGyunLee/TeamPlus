import React, { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { router } from 'expo-router';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';
import { Badge, Button, Card, Chip, Empty, Row, Screen, Section, T } from '../src/components/ui';
import { Confirm } from '../src/components/Confirm';
import { useApp } from '../src/state/AppProvider';
import { useTheme } from '../src/theme/theme';
import { book, isOccupied } from '../src/domain/booking';
import { dateAt, HOURS, hourLabel, localDate, ROOMS } from '../src/domain/model';
export default function Booking() {
  const { data, update } = useApp(); const { colors: c } = useTheme();
  const [groupId, setGroupId] = useState(data?.groups[0]?.id ?? ''); const [roomId, setRoomId] = useState(ROOMS[0]!.id);
  const [date, setDate] = useState(dateAt(1)); const [hour, setHour] = useState<number | null>(null);
  const [confirm, setConfirm] = useState(false); const [success, setSuccess] = useState(false); const [error, setError] = useState('');
  if (!data) return null;
  const group = data.groups.find(g => g.id === groupId) ?? data.groups[0]; const room = ROOMS.find(r => r.id === roomId)!;
  if (!group) return <Screen back title="집현전 가상 예약"><Empty title="모임이 먼저 필요해요" description="홈에서 모임을 만들고 팀원을 추가해 주세요."/><Button onPress={() => router.replace('/')}>홈으로</Button></Screen>;
  function submit() {
    if (hour === null || !group) return;
    try { update(d => book(d, { groupId: group.id, roomId, date, hour })); setConfirm(false); setSuccess(true); setError(''); }
    catch (e) { setConfirm(false); setError(e instanceof Error ? e.message : '예약에 실패했어요.'); setHour(null); }
  }
  function resetSelection() { setHour(null); setError(''); }
  if (success) return <Screen back title="함께할 공간이 준비됐어요" eyebrow="VIRTUAL BOOKING"><Animated.View entering={FadeIn.duration(180).reduceMotion(ReduceMotion.System)}><Card><Badge tone="success">가상 예약 완료</Badge><T size={28} bold>집현전 {room.name}</T><T>{date} · {hourLabel(hour!)}</T><T muted>{group.name} · {group.members.length}명</T><T size={12} muted>실제 집현전 예약 효력은 없습니다. 기기에 저장된 시연용 예약입니다.</T></Card></Animated.View><Button onPress={() => router.replace('/reservations')}>내 가상 예약 보기</Button><Button variant="outline" onPress={() => { setSuccess(false); resetSelection(); }}>다른 시간 예약</Button></Screen>;
  return <Screen back title="집현전 가상 예약" eyebrow="MAKE ROOM FOR IDEAS"><Card style={{ backgroundColor: c.warningBg }}><T size={13} bold color={c.warning}>시연용 가상 예약</T><T size={12} color={c.warning}>실제 예약 시스템과 연동되지 않습니다. 호실과 운영시간은 시연을 위한 예시입니다.</T></Card>
    <Section title="01. 모임 선택"/><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>{data.groups.map(g => <Chip key={g.id} label={`${g.name || '모임'} · ${g.members.length}명`} selected={g.id === group.id} onPress={() => { setGroupId(g.id); resetSelection(); }}/>)}</ScrollView>
    <Section title="02. 인실 · 호실"/><Row style={{ flexWrap: 'wrap', gap: 8 }}>{ROOMS.map(r => <Chip key={r.id} label={`${r.capacity}인실 · ${r.name}`} selected={r.id === roomId} onPress={() => { setRoomId(r.id); resetSelection(); }}/>)}</Row>
    {group.members.length > room.capacity && <T size={13} color={c.warning}>모임 {group.members.length}명이 함께 들어갈 수 있는 인실을 선택해 주세요.{group.members.length > 8 ? ' 시연용 최대 인실은 8인실입니다.' : ''}</T>}
    <Section title="03. 날짜 선택" extra="오늘부터 30일"/><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>{Array.from({ length: 30 }, (_, i) => dateAt(i)).map(d => { const day = new Date(`${d}T12:00:00`); return <Chip key={d} label={`${d.slice(5).replace('-', '/')} ${['일','월','화','수','목','금','토'][day.getDay()]}`} accessibilityLabel={`예약 날짜 ${d}`} selected={date === d} onPress={() => { setDate(d); resetSelection(); }}/>; })}</ScrollView>
    <Section title="04. 시간 선택" extra="1시간 단위"/><T size={12} muted>{date} · {room.name} · 수업 교시와 별개로 운영되는 가상 슬롯입니다.</T>
    <View style={{ gap: 10 }}>{HOURS.map(h => {
      const mine = data.reservations.some(r => r.status === 'active' && r.roomId === roomId && r.date === date && r.hour === h);
      const occupied = isOccupied(data.reservations, { groupId: group.id, roomId, date, hour: h });
      const past = date < localDate() || (date === localDate() && h <= new Date().getHours());
      const groupConflict = data.reservations.some(r => r.status === 'active' && r.groupId === group.id && r.date === date && r.hour === h);
      const disabled = occupied || past || groupConflict || group.members.length > room.capacity;
      const label = past ? '지난 시간' : mine ? '내 예약' : occupied ? '예약됨' : groupConflict ? '모임 예약 있음' : '예약 가능';
      return <Button key={h} variant="outline" disabled={disabled} accessibilityLabel={`${hourLabel(h)} ${label}`} onPress={() => { setHour(h); setError(''); }}><Row style={{ flex: 1, justifyContent: 'space-between' }}><T size={14} bold color={hour === h ? c.primary : c.foreground}>{hourLabel(h)}</T><Badge tone={hour === h ? 'primary' : disabled ? 'muted' : 'success'}>{hour === h ? '선택됨' : label}</Badge></Row></Button>;
    })}</View>
    {error !== '' && <T accessibilityRole="alert" color={c.warning}>{error}</T>}
    <Button disabled={hour === null || group.members.length > room.capacity} onPress={() => setConfirm(true)}>선택한 시간 확인</Button>
    <Confirm visible={confirm} title="가상 예약을 확정할까요?" confirmLabel="가상 예약 확정" onCancel={() => setConfirm(false)} onConfirm={submit}><T bold>집현전 {room.name} · {room.capacity}인실</T><T>{date}{'\n'}{hour !== null ? hourLabel(hour) : ''}</T><T muted>{group.name} · {group.members.length}명</T><T size={12} muted>실제 예약 효력은 없습니다. 내 예약에서 언제든 취소할 수 있어요.</T></Confirm>
  </Screen>;
}
