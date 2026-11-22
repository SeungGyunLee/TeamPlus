import type { Assignment, AvailabilityBlock, Candidate } from '../data/api';
import type { Group } from './model';
import { isIsoDate, kstDateAt } from './apiDates';

export function selectedParticipants(memberIds: string[], excludedIds: string[]) {
  const selected = memberIds.filter(id => !excludedIds.includes(id));
  // A team edit may remove the only selected member while this screen is open.
  return selected.length ? selected : memberIds;
}

export function selectedAvailability(blocks: AvailabilityBlock[], memberIds: string[]) {
  const selected = new Set(memberIds);
  return blocks.map(block => {
    const availableMemberIds = block.availableMemberIds.filter(id => selected.has(id));
    const unavailableMemberIds = block.unavailableMemberIds.filter(id => selected.has(id));
    const count = availableMemberIds.length;
    const total = selected.size;
    const level: AvailabilityBlock['level'] = total > 0 && count === total ? 'full' : count > 0 ? 'partial' : 'none';
    return { ...block, availableMemberIds, unavailableMemberIds, count, total, level };
  }).sort((a, b) => b.count - a.count || a.day - b.day || a.period - b.period);
}

export interface StageProgress { completed: boolean; note: string }
export interface ProjectProgress { version: 1; stages: Record<string, StageProgress> }

export function stageKey(stage: Assignment['stages'][number]) {
  // Deadline edits change date ranges, while the same stage retains its progress.
  return JSON.stringify([stage.position, stage.name, stage.purpose, stage.priority]);
}

export function timelineSummary(assignment: Assignment, progress: ProjectProgress, today = kstDateAt()) {
  const stages = assignment.stages.filter(stage => !stage.dropped).sort((a, b) => a.position - b.position);
  const completed = stages.filter(stage => progress.stages[stageKey(stage)]?.completed).length;
  const next = stages.find(stage => !progress.stages[stageKey(stage)]?.completed);
  const daysLeft = assignment.finalDeadline && isIsoDate(assignment.finalDeadline) && isIsoDate(today)
    ? Math.round((Date.parse(assignment.finalDeadline) - Date.parse(today)) / 86_400_000) : null;
  return { stages, completed, total: stages.length, next, daysLeft,
    percent: stages.length ? Math.round(completed * 100 / stages.length) : 0 };
}

export interface RecommendationContext {
  assignmentTitle: string;
  stageName: string;
  purpose: string;
  preparation: string;
}

export interface ShareDraft {
  kind: 'meeting' | 'project';
  title: string;
  details: string;
  purpose: string;
  preparation: string;
}

export function meetingShareDraft(candidate: Candidate, group: Group, context?: RecommendationContext): ShareDraft {
  const names = (ids: string[]) => ids.map(id => group.members.find(member => member.id === id)?.name || '팀원').join(' · ') || '없음';
  return {
    kind: 'meeting', title: group.name + ' 모임 제안',
    details: [
      '모임 · ' + group.name,
      '일시 · ' + candidate.date + ' ' + candidate.label + ' (한국 시간)',
      '추천 장소 · ' + candidate.room.fullName,
      '참석 가능 · ' + names(candidate.availableMemberIds),
      '참석 어려움 · ' + names(candidate.unavailableMemberIds),
      ...(context ? ['과제 · ' + context.assignmentTitle, '회의 단계 · ' + context.stageName] : []),
    ].join('\n'),
    purpose: context?.purpose ?? '', preparation: context?.preparation ?? '',
  };
}

export function projectShareDraft(assignment: Assignment, progress: ProjectProgress): ShareDraft {
  const summary = timelineSummary(assignment, progress);
  const steps = summary.stages.map(stage => {
    const saved = progress.stages[stageKey(stage)];
    return [
      (saved?.completed ? '✓ ' : '□ ') + stage.name,
      stage.windowStart && stage.windowEnd ? '권장 기간 · ' + stage.windowStart + ' ~ ' + stage.windowEnd : '권장 기간 미정',
      ...(saved?.note ? ['준비물·메모 · ' + saved.note] : []),
    ].join('\n');
  });
  return {
    kind: 'project', title: assignment.title?.trim() || '과제 진행 현황',
    details: ['마감일 · ' + (assignment.finalDeadline ?? '미정'),
      '내 진행률 · ' + summary.completed + '/' + summary.total + '단계 (' + summary.percent + '%)', ...steps].join('\n\n'),
    purpose: '', preparation: '',
  };
}

export function shareMessage(draft: ShareDraft) {
  return [
    '[TeamPlus] ' + (draft.title.trim() || (draft.kind === 'meeting' ? '모임 제안' : '과제 진행 현황')),
    draft.details,
    ...(draft.purpose.trim() ? ['목적 · ' + draft.purpose.trim()] : []),
    ...(draft.preparation.trim() ? ['준비물 · ' + draft.preparation.trim()] : []),
    draft.kind === 'meeting' ? '추천 장소의 실제 예약 여부는 별도로 확인해 주세요.' : '진행 현황은 이 기기에 기록한 내용입니다.',
  ].join('\n\n');
}
