import React, { useCallback, useState } from 'react';
import { View } from 'react-native';
import { api } from '../data/api';
import { kstDateAt } from '../domain/apiDates';
import { useResource } from '../state/apiHooks';
import { DateChoices, RequestFeedback } from './ApiUi';
import { Badge, Card, Section, T } from './ui';

const states = { past: '지난 시간', mine: '시연 예약', occupied: '시연 점유', group_conflict: '모임 일정 겹침', available: '시연 빈 시간' };

export function RoomAvailability({ placeId }: { placeId: string }) {
  const [date, setDate] = useState(kstDateAt);
  const rooms = useResource(useCallback(signal => api?.rooms(signal), []));
  const availability = useResource(useCallback(signal => api?.roomAvailability(date, undefined, signal), [date]));
  const listed = rooms.value?.filter(room => room.placeId === placeId);
  return <>
    <Section title="호실별 시연 가능 시간"/>
    <T size={13} muted>실제 가능 시간과 예약은 중앙도서관 앱에서 확인해 주세요.</T>
    <DateChoices label="조회 날짜" value={date} onChange={setDate}/>
    <RequestFeedback loading={rooms.loading} error={rooms.error} retry={rooms.reload}/>
    <RequestFeedback loading={availability.loading} error={availability.error} retry={availability.reload}/>
    {listed?.map(room => {
      const slots = availability.value?.find(entry => entry.roomId === room.id)?.slots ?? [];
      return <Card key={room.id}><T bold>{room.fullName} · {room.capacity}인실</T>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {slots.map(slot => <Badge key={slot.hour} tone={slot.selectable ? 'success' : 'muted'}>{slot.label} · {states[slot.state]}</Badge>)}
        </View>
      </Card>;
    })}
    {listed?.length === 0 && <T muted>조회할 수 있는 호실이 없어요.</T>}
  </>;
}
