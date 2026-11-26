import React, { useState } from 'react';
import { Share } from 'react-native';
import { useShareDraft } from '../src/state/ShareProvider';
import { useTask } from '../src/state/apiHooks';
import { shareMessage, ShareDraft } from '../src/domain/collaboration';
import { Button, Card, Empty, Field, Screen, T } from '../src/components/ui';
import { RequestFeedback } from '../src/components/ApiUi';

function SharePreview({ initial }: { initial: ShareDraft }) {
  const [draft, setDraft] = useState(initial);
  const task = useTask();
  const message = shareMessage(draft);
  return <Screen back title={draft.kind === 'meeting' ? '모임 제안 공유' : '과제 진행 공유'}>
    <Field accessibilityLabel="공유 제목" value={draft.title} maxLength={120} editable={!task.busy}
      onChangeText={title => setDraft(value => ({ ...value, title }))} placeholder="공유 제목"/>
    <Field accessibilityLabel="공유 목적" value={draft.purpose} maxLength={500} editable={!task.busy}
      onChangeText={purpose => setDraft(value => ({ ...value, purpose }))} placeholder="목적 (선택)"/>
    <Field accessibilityLabel="공유 준비물" value={draft.preparation} maxLength={1000} multiline editable={!task.busy}
      onChangeText={preparation => setDraft(value => ({ ...value, preparation }))} placeholder="준비물 (선택)"
      style={{ minHeight: 88, textAlignVertical: 'top' }}/>
    <Card><T bold>공유 미리보기</T><T selectable>{message}</T></Card>
    <T muted size={13}>공유창에서 보낼 앱과 대상을 선택해 주세요.</T>
    <RequestFeedback error={task.error}/>
    <Button disabled={task.busy} onPress={() => void task.run(async () => {
      try { await Share.share({ title: draft.title, message }); }
      catch { throw new Error('공유창을 열지 못했어요. 다시 시도해 주세요.'); }
    })}>{task.busy ? '공유창 여는 중…' : '공유하기'}</Button>
  </Screen>;
}

export default function ShareScreen() {
  const { draft } = useShareDraft();
  if (!draft) return <Screen back title="공유"><Empty title="공유할 내용이 없어요" description="추천 장소나 과제에서 공유하기를 눌러 주세요."/></Screen>;
  return <SharePreview key={JSON.stringify(draft)} initial={draft}/>;
}
