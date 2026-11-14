import React, { useState } from 'react';
import { View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { api } from '../../src/data/api';
import type { Conditions, ConditionsResponse } from '../../src/data/api';
import { DataSource, DateChoices, RequestFeedback } from '../../src/components/ApiUi';
import { Button, Card, Empty, Field, Screen, T } from '../../src/components/ui';
import { kstDateAt, recommendationRangeError } from '../../src/domain/apiDates';
import { useGroup, useTask } from '../../src/state/apiHooks';
import { useRecommendation } from '../../src/state/RecommendationProvider';

const sample = '3명 모두 참석할 수 있고 콘센트가 있는 조용한 장소 추천해 줘.';

export default function Recommend() {
  const { id, dateFrom, dateTo } = useLocalSearchParams<{ id: string; dateFrom?: string; dateTo?: string }>();
  const group = useGroup(id);
  const { setResult } = useRecommendation();
  const task = useTask();
  const [text, setText] = useState('');
  const [history, setHistory] = useState('');
  const [answer, setAnswer] = useState('');
  const [question, setQuestion] = useState<ConditionsResponse>();
  const [conditions, setConditions] = useState<Conditions>();
  const [from, setFrom] = useState(dateFrom ?? kstDateAt());
  const [to, setTo] = useState(dateTo ?? kstDateAt(6));
  const rangeError = recommendationRangeError(from, to);
  const followup = question ? history + '\n추가 질문: ' + (question.question ?? '') + '\n답변: ' + answer.trim() : text.trim();
  const inputError = followup.length > 500 ? '조건과 추가 답변을 합쳐 500자 이내로 줄여 주세요.' : '';
  const canSubmit = !!text.trim() && (!question || !!answer.trim()) && !rangeError && !inputError && !task.busy;

  function resetInterpretation() {
    setHistory('');
    setQuestion(undefined);
    setAnswer('');
    setConditions(undefined);
  }

  function submit() {
    const server = api;
    if (!server || !canSubmit) return;
    void task.run(async () => {
      let resolved = conditions;
      if (!resolved) {
        const parsed = await server.conditions(id, followup);
        if (parsed.type === 'question') {
          setHistory(followup);
          setQuestion(parsed);
          setAnswer('');
          return;
        }
        resolved = parsed.conditions;
        setConditions(resolved);
        setQuestion(undefined);
      }
      const response = await server.recommendations(id, resolved, from, to);
      setResult({ groupId: id, from, to, response });
      router.push({ pathname: '/recommend-results/[id]', params: { id } });
    });
  }

  return <Screen back title="조건으로 장소 추천">
    <DataSource/>
    {!api ? <Empty title="서버 연결이 필요해요" description="TeamPlus 서버 주소를 설정한 후 이용할 수 있어요."/>
      : group.loading || group.error ? <RequestFeedback loading={group.loading} error={group.error} retry={group.reload}/>
      : !group.group ? <Empty title="모임을 찾을 수 없어요" description="홈에서 모임을 선택해 주세요."/>
      : <>
        <T muted>{group.group.name} · 팀원 {group.group.members.length}명</T>
        <Field multiline maxLength={500} editable={!task.busy} accessibilityLabel="추천 조건" placeholder={sample} value={text}
          onChangeText={value => { setText(value); resetInterpretation(); }} style={{ minHeight: 108, textAlignVertical: 'top' }}/>
        <Button variant="ghost" disabled={task.busy} onPress={() => { setText(sample); resetInterpretation(); }}>예시로 입력</Button>
        <View pointerEvents={task.busy ? 'none' : 'auto'} style={{ gap: 14 }}>
          <DateChoices label="시작일" value={from} onChange={value => { setFrom(value); if (to < value) setTo(value); }}/>
          <DateChoices label="종료일" value={to} minimum={from} onChange={setTo}/>
        </View>
        {(rangeError || inputError) && <T accessibilityRole="alert" muted>{rangeError || inputError}</T>}
        {question && <Card><T bold>{question.question || '추천에 필요한 조건을 조금 더 알려 주세요.'}</T>
          <Field value={answer} onChangeText={setAnswer} editable={!task.busy} maxLength={500} placeholder="추가 답변" accessibilityLabel="추가 답변"/>
          <Button variant="ghost" disabled={task.busy} onPress={resetInterpretation}>처음 조건으로 돌아가기</Button>
        </Card>}
        <RequestFeedback loading={task.busy} error={task.error}/>
        {task.busy && <T muted>서버에서 조건과 가능한 장소를 확인하고 있어요.</T>}
        <Button disabled={!canSubmit} onPress={submit}>{task.error ? '다시 시도' : question ? '추가 답변 보내기' : '장소 추천받기'}</Button>
      </>}
  </Screen>;
}
