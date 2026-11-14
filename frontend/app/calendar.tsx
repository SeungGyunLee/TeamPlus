import React from 'react';
import { Linking, Platform } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { startActivityAsync } from 'expo-intent-launcher';
import { Card, Button, Empty, Screen, T } from '../src/components/ui';
import { RequestFeedback } from '../src/components/ApiUi';
import { calendarTimes } from '../src/domain/apiDates';
import { hourLabel } from '../src/domain/model';
import { useTask } from '../src/state/apiHooks';

export default function CalendarEvent() {
  const { place, date, hour } = useLocalSearchParams<{ place?: string; date?: string; hour?: string }>();
  const task = useTask();
  const times = calendarTimes(date ?? '', Number(hour));
  if (!times || !place) return <Screen back title="일정 추가"><Empty title="일정 정보가 없어요" description="추천 장소에서 다시 선택해 주세요."/></Screen>;
  const title = 'KW Meet 모임';
  const desc = 'KW Meet에서 고른 모임 일정입니다. 집현전 예약은 중앙도서관 앱에서 진행해 주세요.';
  const calendarDate = (timestamp: number) => new Date(timestamp).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  const eventTimes = times;
  const eventPlace = place;
  function addEvent(web = false) {
    void task.run(async () => {
      try {
        if (!web && Platform.OS === 'android') {
          await startActivityAsync('android.intent.action.INSERT', {
            data: 'content://com.android.calendar/events',
            type: 'vnd.android.cursor.dir/event',
            extra: { title, eventLocation: eventPlace, description: desc, beginTime: eventTimes.start, endTime: eventTimes.end },
          });
          return;
        }
      } catch {
        // A device without a calendar handler can still open Google's event form.
      }
      const params = new URLSearchParams({ action: 'TEMPLATE', text: title, details: desc, location: eventPlace,
        dates: calendarDate(eventTimes.start) + '/' + calendarDate(eventTimes.end), ctz: 'Asia/Seoul' });
      try { await Linking.openURL('https://calendar.google.com/calendar/render?' + params.toString()); }
      catch { throw new Error('캘린더를 열 수 없어요. 앱 설치나 브라우저 연결을 확인해 주세요.'); }
    });
  }
  return <Screen back title="일정 추가">
    <Card><T bold>{title}</T><T>{date} · {hourLabel(Number(hour))} (한국 시간)</T><T>{place}</T></Card>
    <T muted>캘린더에서 일정을 확인한 뒤 저장해 주세요.</T>
    <RequestFeedback loading={task.busy} error={task.error}/>
    <Button disabled={task.busy} onPress={() => addEvent()}>일정 추가</Button>
    <Button variant="outline" disabled={task.busy} onPress={() => addEvent(true)}>Google 캘린더 열기</Button>
    <Button variant="outline" disabled={task.busy} onPress={() => router.back()}>나중에 하기</Button>
  </Screen>;
}
