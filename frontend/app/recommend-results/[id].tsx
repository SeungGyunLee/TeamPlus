import React from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { DataSource, RequestFeedback } from '../../src/components/ApiUi';
import { Badge, Card, Empty, LinkRow, Row, Screen, T } from '../../src/components/ui';
import { useGroup } from '../../src/state/apiHooks';
import { useRecommendation } from '../../src/state/RecommendationProvider';

export default function RecommendationResults() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { result } = useRecommendation();
  const group = useGroup(id);
  const response = result?.groupId === id ? result.response : undefined;
  const names = (ids: string[]) => ids.map(id => group.group?.members.find(member => member.id === id)?.name || '팀원').join(' · ') || '없음';

  return <Screen back title="장소 추천 결과">
    <DataSource/>
    <RequestFeedback loading={group.loading} error={group.error} retry={group.reload}/>
    {!response ? <Empty title="추천 결과가 없어요" description="조건 입력 화면으로 돌아가 추천을 요청해 주세요."/> : <>
      <T muted>{result?.from} ~ {result?.to}</T>
      {response.reasonsSource === 'fallback' && <T muted>서버의 기본 추천 이유를 표시하고 있어요.</T>}
      {response.reasonsSource === 'partial' && <T muted>일부 추천에는 서버의 기본 이유가 표시돼요.</T>}
      {!response.candidates.length && <Empty title="맞는 장소를 찾지 못했어요" description="날짜 범위를 넓히거나 조건을 바꿔 다시 추천받아 보세요."/>}
      {response.candidates.map(candidate => <Card key={candidate.candidateId}>
        <Row style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <Badge tone={candidate.status === 'green' ? 'success' : 'warning'}>{candidate.status === 'green' ? '전원 가능 · 조건 충족' : '조건 또는 일정 조정 필요'}</Badge>
          <T bold>{candidate.score} / 100점</T>
        </Row>
        <T size={20} bold>{candidate.room.fullName}</T>
        <T>{candidate.date} · {candidate.label}</T>
        {group.group && <>
          <T size={13}>참석 가능 · {names(candidate.availableMemberIds)}</T>
          <T size={13} muted>참석 어려움 · {names(candidate.unavailableMemberIds)}</T>
        </>}
        <T size={13}>조건 충족 · {candidate.conditionsMet.join(' · ') || '없음'}</T>
        {!!candidate.conflicts.length && <T size={13} muted>{candidate.conflicts.join(' · ')}</T>}
        {candidate.reason && <T size={13}>{candidate.reason}</T>}
        <T size={12} muted>{candidate.room.capacity}인실 · {candidate.room.noiseLevel === 'quiet' ? '조용함' : '일반 소음'} · {candidate.room.hasOutlet ? '콘센트 있음' : '콘센트 없음'} · {candidate.room.laptopSpace ? '노트북 공간 있음' : '노트북 공간 없음'}</T>
        <LinkRow title="추천 장소 상세" description="도서관 앱과 캘린더 연결" onPress={() => router.push({ pathname: '/recommend-detail/[id]', params: { id, candidateId: candidate.candidateId } })}/>
      </Card>)}
    </>}
  </Screen>;
}
