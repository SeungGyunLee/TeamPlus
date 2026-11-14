import React from 'react';
import { ScrollView, View } from 'react-native';
import { api, usesTestAi } from '../data/api';
import { kstDateAt } from '../domain/apiDates';
import { Badge, Button, Card, Chip, Loading, T } from './ui';

export function DataSource() {
  return <Badge tone={api ? 'primary' : 'muted'}>{api ? usesTestAi ? '로컬 서버 · AI 테스트 응답' : 'TeamPlus 서버' : '기기 내 시연 데이터'}</Badge>;
}

export function RequestFeedback({ loading, error, retry }: { loading?: boolean; error?: string; retry?: () => void }) {
  if (loading) return <Loading/>;
  if (!error) return null;
  return <Card><T accessibilityRole="alert">{error}</T>{retry && <Button variant="outline" onPress={retry}>다시 시도</Button>}</Card>;
}

export function DateChoices({ label, value, onChange, minimum }: { label: string; value: string; onChange: (value: string) => void; minimum?: string }) {
  const dates = Array.from({ length: 30 }, (_, index) => kstDateAt(index)).filter(date => !minimum || date >= minimum);
  return <View style={{ gap: 8 }}><T bold>{label} · {value}</T>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
      {dates.map(date => <Chip key={date} label={date.slice(5)} accessibilityLabel={label + ' ' + date} selected={date === value} onPress={() => onChange(date)}/>)}
    </ScrollView>
  </View>;
}
