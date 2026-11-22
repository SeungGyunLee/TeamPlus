import { useCallback, useEffect, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ProgressRepository, progressStorageKey } from '../data/progressRepository';
import { errorMessage } from '../data/api';
import { ProjectProgress, StageProgress } from '../domain/collaboration';

const repository = new ProgressRepository(AsyncStorage);
const scope = process.env.EXPO_PUBLIC_API_URL?.trim() || 'device';

export function useProjectProgress(groupId: string, assignmentId: number) {
  const key = progressStorageKey(scope, groupId, assignmentId);
  const [state, setState] = useState<{ key: string; progress?: ProjectProgress; error?: string; saveError?: string; saving: boolean }>({ key, saving: false });
  const current = useRef<{ key: string; progress: ProjectProgress } | null>(null);
  const revision = useRef(0);
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    const version = ++revision.current;
    current.current = null;
    setState({ key, saving: false });
    void repository.load(key).then(progress => {
      if (revision.current !== version) return;
      current.current = { key, progress };
      setState({ key, progress, saving: false });
    }).catch(error => {
      if (revision.current === version) setState({ key, error: errorMessage(error), saving: false });
    });
    return () => { revision.current++; current.current = null; };
  }, [key, reloadCount]);

  const persist = useCallback((progress: ProjectProgress) => {
    const version = ++revision.current;
    setState({ key, progress, saving: true });
    void repository.save(key, progress).then(() => {
      if (revision.current === version) setState({ key, progress, saving: false });
    }).catch(() => {
      if (revision.current === version) setState({ key, progress, saving: false, saveError: '진행 현황을 저장하지 못했어요. 다시 저장해 주세요.' });
    });
  }, [key]);

  function updateStage(stageId: string, change: Partial<StageProgress>) {
    const saved = current.current;
    if (!saved || saved.key !== key) return;
    const progress: ProjectProgress = { ...saved.progress, stages: { ...saved.progress.stages,
      [stageId]: { completed: false, note: '', ...saved.progress.stages[stageId], ...change } } };
    current.current = { key, progress };
    persist(progress);
  }

  return {
    progress: state.key === key ? state.progress : undefined,
    error: state.key === key ? state.error : undefined,
    saveError: state.key === key ? state.saveError : undefined,
    saving: state.key === key && state.saving,
    updateStage,
    reload: () => setReloadCount(value => value + 1),
    retrySave: () => { if (current.current?.key === key) persist(current.current.progress); },
  };
}
