import React, { useState } from 'react';
import { router } from 'expo-router';
import { Badge, Button, Card, Chip, Empty, Row, Screen, T } from '../../src/components/ui';
import { Confirm } from '../../src/components/Confirm';
import { useApp } from '../../src/state/AppProvider';
import { cancel } from '../../src/domain/booking';
import { hourLabel, ROOMS } from '../../src/domain/model';
export default function Reservations() {
  const { data, update } = useApp(); const [filter, setFilter] = useState<'active' | 'cancelled'>('active'); const [cancelId, setCancelId] = useState<string | null>(null);
  const items = data?.reservations.filter(r => r.status === filter) ?? [];
  return <Screen title="내 가상 예약" eyebrow="YOUR NEXT GATHERING"><T muted>모임을 위한 공간과 시간을 한눈에.{'\n'}실제 집현전 예약 효력은 없습니다.</T><Row><Chip label="예약 내역" selected={filter === 'active'} onPress={() => setFilter('active')}/><Chip label="취소 내역" selected={filter === 'cancelled'} onPress={() => setFilter('cancelled')}/></Row>
    {!items.length && <Empty title={filter === 'active' ? '아직 예약한 공간이 없어요' : '취소한 예약이 없어요'} description={filter === 'active' ? '장소 탐색에서 집현전을 선택해 가상 예약을 시작해 보세요.' : '취소한 예약은 이곳에 기록됩니다.'}/>}
    {items.map(r => <Card key={r.id}><Badge tone={r.status === 'active' ? 'success' : 'muted'}>{r.status === 'active' ? '가상 예약 확정' : '취소 완료'}</Badge><T size={23} bold>집현전 {ROOMS.find(room => room.id === r.roomId)?.name ?? r.roomId}</T><T>{r.date} · {hourLabel(r.hour)}</T><T size={13} muted>{r.groupName}</T><T size={10} muted>예약 번호 {r.id}</T>{r.status === 'active' && <Button variant="outline" onPress={() => setCancelId(r.id)}>예약 취소</Button>}</Card>)}
    <Button variant="outline" onPress={() => router.push('/places')}>공간 둘러보기</Button>
    <Confirm visible={!!cancelId} title="가상 예약을 취소할까요?" confirmLabel="예약 취소 확정" onCancel={() => setCancelId(null)} onConfirm={() => { update(d => cancel(d, cancelId!)); setCancelId(null); }}><T muted>취소하면 다른 시간으로 다시 예약할 수 있어요. 취소 내역은 기기에 남습니다.</T></Confirm>
  </Screen>;
}
