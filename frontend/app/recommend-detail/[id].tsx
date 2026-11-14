import React, { useCallback } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { api } from '../../src/data/api';
import { RequestFeedback } from '../../src/components/ApiUi';
import { LibraryLink } from '../../src/components/LibraryLink';
import { Button, Card, Empty, Screen, T } from '../../src/components/ui';
import { useResource } from '../../src/state/apiHooks';
import { useRecommendation } from '../../src/state/RecommendationProvider';

export default function RecommendationDetail() {
  const { id, candidateId } = useLocalSearchParams<{ id: string; candidateId: string }>();
  const { result } = useRecommendation();
  const candidate = result?.groupId === id ? result.response.candidates.find(item => item.candidateId === candidateId) : undefined;
  const placeId = candidate?.room.placeId;
  const place = useResource(useCallback(signal => placeId ? api?.place(placeId, signal) : undefined, [placeId]));
  if (!candidate) return <Screen back title="추천 장소"><Empty title="선택한 추천이 없어요" description="추천 목록에서 다시 선택해 주세요."/></Screen>;
  return <Screen back title={candidate.room.fullName}>
    <Card><T bold>{candidate.date} · {candidate.label}</T>
      <T>{candidate.room.capacity}인실 · 추천 점수 {candidate.score} / 100</T>
      {candidate.reason && <T muted>{candidate.reason}</T>}
    </Card>
    <RequestFeedback loading={place.loading} error={place.error} retry={place.reload}/>
    {place.value && <Card><T bold>{place.value.name} · {candidate.room.name}</T><T>{place.value.location}</T><T>{place.value.description}</T><T muted>{place.value.note}</T></Card>}
    <T muted>표시된 호실과 가능 시간은 시연용입니다. 실제 예약과 현황 확인은 중앙도서관 앱에서 진행해 주세요.</T>
    <LibraryLink/>
    <Button variant="outline" onPress={() => router.push({ pathname: '/calendar', params: {
      place: candidate.room.fullName, date: candidate.date, hour: String(candidate.hour),
    } })}>캘린더에 일정 추가</Button>
  </Screen>;
}
