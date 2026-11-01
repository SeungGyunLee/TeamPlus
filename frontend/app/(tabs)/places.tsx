import React, { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowUpRight, MapPin } from 'lucide-react-native';
import { Badge, Button, Card, Chip, Empty, Field, Loading, Row, Screen, T } from '../../src/components/ui';
import { Place } from '../../src/domain/model';
import { useApp } from '../../src/state/AppProvider';
import { useTheme } from '../../src/theme/theme';
export default function Places() {
  const { repository } = useApp(); const { colors: c } = useTheme();
  const [places, setPlaces] = useState<Place[] | null>(null); const [error, setError] = useState(false); const [query, setQuery] = useState(''); const [category, setCategory] = useState('전체');
  function load() { setError(false); void repository.places().then(setPlaces).catch(() => setError(true)); }
  useEffect(load, [repository]);
  const filtered = places?.filter(p => (category === '전체' || p.category === category) && `${p.name} ${p.tags.join(' ')}`.includes(query.trim()));
  return <Screen title="머물고 싶은 공간" eyebrow="PLACES FOR YOUR TEAM"><T muted>함께 집중할 곳을 찾아보세요.{'\n'}현재는 시연용 장소 목록을 제공해요.</T>
    <Field accessibilityLabel="장소 검색" placeholder="공간 이름이나 특징 검색" value={query} onChangeText={setQuery}/><Row>{['전체','교내','카페'].map(x => <Chip key={x} label={x} selected={category === x} onPress={() => setCategory(x)}/>)}</Row>
    {error ? <Card><T>장소를 불러오지 못했어요.</T><Button onPress={load}>다시 시도</Button></Card> : !places ? <Loading/> : !filtered?.length ? <Empty title="일치하는 공간이 없어요" description="검색어나 분류를 바꿔 다시 찾아보세요."/> : filtered.map((p, index) => <Pressable key={p.id} accessibilityRole="button" accessibilityLabel={`${p.name} 상세 보기`} onPress={() => router.push({ pathname: '/place/[id]', params: { id: p.id } })}><Card style={{ padding: 0, overflow: 'hidden' }}>
      <View style={{ padding: 22, backgroundColor: c.elevated, minHeight: 125, justifyContent: 'space-between' }}><Row style={{ justifyContent: 'space-between' }}><T size={11} muted style={{ letterSpacing: 2 }}>{p.category === '교내' ? 'ON CAMPUS' : 'AROUND CAMPUS'}</T><T size={36} color={c.primary} style={{ opacity: 0.5 }}>0{index + 1}</T></Row><Row style={{ justifyContent: 'space-between' }}><T size={25} bold>{p.name}</T><ArrowUpRight size={23} color={c.primary}/></Row></View>
      <View style={{ paddingHorizontal: 20, paddingBottom: 20, gap: 14 }}><Row><MapPin size={14} color={c.muted}/><T size={12} muted style={{ flex: 1 }}>{p.location}</T></Row><Row style={{ flexWrap: 'wrap', gap: 7 }}>{p.tags.map(tag => <Badge key={tag} tone="muted">{tag}</Badge>)}</Row><T size={12} muted>최대 {p.capacity}명 · {p.reservable ? '가상 예약 가능' : '공간 정보'}</T></View>
    </Card></Pressable>)}
  </Screen>;
}
