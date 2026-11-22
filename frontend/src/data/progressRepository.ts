import type { StoragePort } from './repository';
import type { ProjectProgress } from '../domain/collaboration';

export function progressStorageKey(scope: string, groupId: string, assignmentId: number) {
  return 'kw-meet:progress:v1:' + JSON.stringify([scope.replace(/\/+$/, ''), groupId, assignmentId]);
}

export function decodeProgress(raw: string): ProjectProgress {
  const value = JSON.parse(raw) as ProjectProgress;
  if (!value || value.version !== 1 || !value.stages || typeof value.stages !== 'object' || Array.isArray(value.stages)
    || !Object.values(value.stages).every(stage => stage && typeof stage.completed === 'boolean' && typeof stage.note === 'string' && stage.note.length <= 1000)) {
    throw new Error('저장된 진행 현황을 읽을 수 없어요. 기기 저장소를 확인한 뒤 다시 불러와 주세요.');
  }
  return value;
}

export class ProgressRepository {
  private queue: Promise<void> = Promise.resolve();
  constructor(private storage: StoragePort) {}
  async load(key: string): Promise<ProjectProgress> {
    await this.queue.catch(() => {});
    const raw = await this.storage.getItem(key);
    return raw === null ? { version: 1, stages: {} } : decodeProgress(raw);
  }
  save(key: string, progress: ProjectProgress) {
    const snapshot = JSON.stringify(progress);
    const task = this.queue.catch(() => {}).then(() => this.storage.setItem(key, snapshot));
    this.queue = task;
    return task;
  }
}
