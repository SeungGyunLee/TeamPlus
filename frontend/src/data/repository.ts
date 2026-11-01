import { AppData, Group, NEW_GROUP_MEMBER_NAMES, ThemeMode } from '../domain/model';
import { initialData, PLACES } from './seed';
export interface StoragePort { getItem(key: string): Promise<string | null>; setItem(key: string, value: string): Promise<void> }
const KEY = 'kw-meet:v1';
function validGroup(g: unknown): g is Group {
  if (!g || typeof g !== 'object') return false;
  const x = g as Group;
  return typeof x.id === 'string' && typeof x.name === 'string' && typeof x.ownerId === 'string' && typeof x.updatedAt === 'string' && Array.isArray(x.members) && x.members.length > 0 && x.members.every(m => typeof m.id === 'string' && typeof m.name === 'string' && Array.isArray(m.busy) && m.busy.every(k => /^[0-4]-[0-5]$/.test(k)));
}
export function decodeData(raw: string): AppData {
  const x = JSON.parse(raw) as AppData;
  if (x.version !== 1 || !(['light','dark','system'] as ThemeMode[]).includes(x.theme) || !Array.isArray(x.groups) || !x.groups.every(validGroup) || !Array.isArray(x.reservations) || !x.reservations.every(r => typeof r.id === 'string' && typeof r.groupId === 'string' && typeof r.groupName === 'string' && typeof r.roomId === 'string' && typeof r.date === 'string' && Number.isInteger(r.hour) && ['active','cancelled'].includes(r.status))) throw new Error('저장 데이터를 읽을 수 없어요. 원본은 기기에 보존되어 있습니다.');
  return x;
}
export class LocalRepository {
  private queue: Promise<void> = Promise.resolve();
  constructor(private storage: StoragePort) {}
  async load() {
    const raw = await this.storage.getItem(KEY);
    if (raw === null) return initialData();
    const data = decodeData(raw);
    if (data.seedNamesVersion === 2) return data;
    const originalNames: Record<string, { changed: string; original: string }> = {
      min: { changed: '건우', original: '민서' },
      jun: { changed: '승균', original: '준호' },
      seo: { changed: '휘서', original: '서연' },
    };
    const migrated: AppData = { ...data, seedNamesVersion: 2, groups: data.groups.map(group => {
      if (group.name === '새로운 모임' && group.members.length === 3) {
        return { ...group, members: group.members.map((member, index) => ({ ...member, name: NEW_GROUP_MEMBER_NAMES[index]! })) };
      }
      // Undo the previous change to the wrong demo group, preserving custom edits.
      if (data.seedNamesVersion === 1 && group.id === 'first-meet') {
        return { ...group, members: group.members.map(member => {
          const original = originalNames[member.id];
          return original && member.name === original.changed ? { ...member, name: original.original } : member;
        }) };
      }
      return group;
    }) };
    await this.save(migrated);
    return migrated;
  }
  save(data: AppData) {
    const snapshot = JSON.stringify(data);
    const task = this.queue.catch(() => {}).then(() => this.storage.setItem(KEY, snapshot));
    this.queue = task;
    return task;
  }
  async places() { return PLACES; }
}
