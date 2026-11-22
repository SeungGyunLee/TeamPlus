import React from 'react';
import { Pressable, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';
import { router } from 'expo-router';
import { Check } from 'lucide-react-native';
import type { Assignment } from '../data/api';
import { kstDateAt, recommendationRangeError } from '../domain/apiDates';
import { projectShareDraft, stageKey, timelineSummary } from '../domain/collaboration';
import { useProjectProgress } from '../state/useProjectProgress';
import { useShareDraft } from '../state/ShareProvider';
import { useTheme } from '../theme/theme';
import { Badge, Button, Card, Empty, Field, Row, Section, T } from './ui';
import { RequestFeedback } from './ApiUi';

export function ProjectTimeline({ groupId, assignment }: { groupId: string; assignment: Assignment }) {
  const { colors: c } = useTheme();
  const saved = useProjectProgress(groupId, assignment.id);
  const { setDraft } = useShareDraft();
  const progress = saved.progress;
  if (!progress) return <RequestFeedback loading={!saved.error} error={saved.error} retry={saved.reload}/>;
  const summary = timelineSummary(assignment, progress);
  const dueLabel = summary.daysLeft === null ? '마감일 미정'
    : summary.daysLeft < 0 ? `마감 ${-summary.daysLeft}일 지남`
    : summary.daysLeft === 0 ? '오늘 마감' : `D-${summary.daysLeft}`;
  return <View style={{ gap: 20 }}>
    <Card>
      <Row style={{ justifyContent: 'space-between' }}><T bold>내 진행 현황</T><Badge tone="warning">{dueLabel}</Badge></Row>
      <Animated.View key={summary.percent} entering={FadeIn.duration(160).reduceMotion(ReduceMotion.System)}>
        <T size={32} bold>{summary.percent}<T size={16} muted>%</T></T>
      </Animated.View>
      <View accessibilityRole="progressbar" accessibilityLabel="내 과제 진행률" accessibilityValue={{ min: 0, max: 100, now: summary.percent }}
        style={{ height: 10, borderRadius: 5, backgroundColor: c.elevated, overflow: 'hidden' }}>
        <View style={{ width: `${summary.percent}%`, height: '100%', backgroundColor: c.primary }}/>
      </View>
      <T>{summary.completed} / {summary.total}단계 완료</T>
      <T muted>{summary.next ? '다음 단계 · ' + summary.next.name : summary.total ? '모든 단계를 마쳤어요.' : '진행할 단계가 없어요.'}</T>
      <T size={12} muted>완료 체크와 메모는 이 기기에 저장됩니다.</T>
    </Card>
    <RequestFeedback error={saved.saveError} retry={saved.retrySave}/>
    {saved.saving && <T size={12} muted accessibilityLiveRegion="polite">진행 현황 저장 중…</T>}
    <Section title="과제 타임라인"/>
    {!assignment.stages.length && <Empty title="회의 단계가 없어요" description="과제 공지를 확인해 주세요."/>}
    {assignment.stages.map(stage => {
      const key = stageKey(stage);
      const entry = progress.stages[key];
      const completed = !!entry?.completed;
      const from = stage.windowStart ?? '';
      const to = stage.windowEnd ?? '';
      const rangeError = stage.dropped || !from || !to ? '추천할 날짜 범위가 없어요.' : recommendationRangeError(from, to);
      return <View key={key} style={{ borderLeftWidth: 2, borderLeftColor: completed ? c.success : c.border, paddingLeft: 14 }}>
        <Card style={{ borderColor: completed ? c.success : c.border }}>
          <Badge tone={stage.dropped ? 'muted' : completed ? 'success' : stage.priority === 'must' ? 'primary' : 'muted'}>
            {stage.dropped ? '일정에서 제외됨' : completed ? '완료' : stage.priority === 'must' ? '필수' : '선택'}
          </Badge>
          <Pressable accessibilityRole="checkbox" accessibilityLabel={stage.name + ' 완료'}
            accessibilityState={{ checked: completed, disabled: stage.dropped }} disabled={stage.dropped}
            onPress={() => saved.updateStage(key, { completed: !completed })} style={{ minHeight: 48, justifyContent: 'center' }}>
            <Row><View style={{ width: 26, height: 26, borderRadius: 8, borderWidth: 1, borderColor: completed ? c.success : c.border,
              backgroundColor: completed ? c.successBg : c.surface, alignItems: 'center', justifyContent: 'center' }}>
              {completed && <Check size={18} color={c.success}/>}
            </View><T size={18} bold style={{ flex: 1 }}>{stage.name}</T></Row>
          </Pressable>
          <T>{stage.purpose}</T>
          <T muted>{from && to ? `${from} ~ ${to}` : '권장 날짜 미정'}</T>
          {!completed && !stage.dropped && to && to < kstDateAt() && <T size={12} color={c.warning}>권장 기간이 지났어요.</T>}
          {stage.anchoredTo && <T muted size={12}>기준 일정 · {stage.anchoredTo}</T>}
          {!stage.dropped && <Field accessibilityLabel={stage.name + ' 준비물 메모'} multiline maxLength={1000}
            value={entry?.note ?? ''} onChangeText={note => saved.updateStage(key, { note })} placeholder="준비물·메모"
            style={{ minHeight: 80, textAlignVertical: 'top' }}/>}
          {rangeError ? <T muted size={13}>{rangeError}</T> : <Button variant="outline" onPress={() => router.push({
            pathname: '/recommend/[id]', params: { id: groupId, dateFrom: from, dateTo: to,
              assignmentTitle: assignment.title?.trim() || '제목 없는 과제', stageName: stage.name,
              purpose: stage.purpose, preparation: entry?.note ?? '' },
          })}>이 날짜로 장소 추천</Button>}
        </Card>
      </View>;
    })}
    <Button variant="outline" onPress={() => {
      setDraft(projectShareDraft(assignment, progress));
      router.push('/share');
    }}>과제 진행 공유</Button>
  </View>;
}
