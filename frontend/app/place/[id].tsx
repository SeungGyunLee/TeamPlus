import React, { useCallback } from 'react';
import { View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Badge, Button, Card, Empty, Row, Screen, Section, T } from '../../src/components/ui';
import { api } from '../../src/data/api';
import { DataSource, RequestFeedback } from '../../src/components/ApiUi';
import { LibraryLink } from '../../src/components/LibraryLink';
import { RoomAvailability } from '../../src/components/RoomAvailability';
import { useResource } from '../../src/state/apiHooks';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
export default function PlaceDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { repository } = useApp(); const { colors: c } = useTheme();
  const { value: place, loading, error, reload } = useResource(useCallback(signal =>
    api ? api.place(id, signal) : repository.places().then(places => places.find(value => value.id === id)), [id, repository]));
  if (loading || error) return <Screen back title="공간 정보"><RequestFeedback loading={loading} error={error} retry={reload}/></Screen>;
  if (!place) return <Screen back title="공간 정보"><Empty title="공간을 찾을 수 없어요" description="장소 목록에서 다시 선택해 주세요."/></Screen>;
  return <Screen back title={place.name} eyebrow="A SPACE TO GATHER"><DataSource/><Row style={{ flexWrap: 'wrap', gap: 7 }}>{place.tags.map(tag => <Badge key={tag}>{tag}</Badge>)}</Row>
    <View style={{ height: 170, backgroundColor: c.elevated, borderColor: c.border, borderWidth: 1, borderRadius: 14, padding: 24, justifyContent: 'space-between' }}><T size={12} muted style={{ letterSpacing: 3 }}>SPACE / KW MEET</T><T size={32} bold color={c.primary}>{place.reservable ? '작은 공간, 큰 생각.' : '우리의 대화가 시작되는 곳.'}</T></View>
    <T size={18} style={{ lineHeight: 30 }}>{place.description}</T><Section title="공간 안내"/><Card><T bold>위치</T><T muted>{place.location}</T><T bold>수용 인원</T><T muted>최대 {place.capacity}명 · 시연용 기준</T></Card>
    <Card style={{ backgroundColor: c.warningBg, borderColor: c.border }}><T bold size={13} color={c.warning}>시연 데이터 안내</T><T size={13} color={c.warning}>{place.note}</T></Card>
    {place.reservable ? api ? <><LibraryLink/><RoomAvailability placeId={place.id}/></> : <Button onPress={() => router.push('/booking')}>집현전 가상 예약하기</Button> : <Button variant="outline" onPress={() => router.push('/places')}>다른 공간 둘러보기</Button>}
  </Screen>;
}
