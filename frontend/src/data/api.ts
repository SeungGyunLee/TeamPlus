import type { Day, Group, Member, Place, SlotKey } from '../domain/model';

export interface AvailabilityBlock {
  key: SlotKey;
  day: Day;
  period: number;
  periodLabel: string;
  count: number;
  total: number;
  level: 'full' | 'partial' | 'none';
  availableMemberIds: string[];
  unavailableMemberIds: string[];
}

export interface AvailabilityResponse {
  groupId: string;
  total: number;
  fullCount: number;
  blocks: AvailabilityBlock[];
}

export interface ApiRoom {
  id: string;
  placeId: string;
  fullName: string;
  name: string;
  capacity: number;
  hasOutlet: boolean;
  noiseLevel: 'quiet' | 'normal';
  laptopSpace: boolean;
}

export interface RoomAvailability {
  roomId: string;
  roomName: string;
  capacity: number;
  fitsGroup: boolean | null;
  slots: { hour: number; label: string; state: 'past' | 'mine' | 'occupied' | 'group_conflict' | 'available'; selectable: boolean }[];
}

export interface Conditions {
  capacity: number | null;
  noiseLevel: 'quiet' | 'normal' | '무관' | null;
  needsOutlet: boolean | null;
  needsLaptopSpace: boolean | null;
  roomType: 'study_room' | 'reading_room' | '무관' | null;
  timePreference: string | null;
  clarifyingQuestion: string | null;
}

export interface ConditionsResponse {
  type: 'question' | 'conditions';
  conditions: Conditions;
  question: string | null;
}

export interface Candidate {
  candidateId: string;
  room: ApiRoom;
  date: string;
  hour: number;
  label: string;
  score: number;
  status: 'green' | 'orange';
  availableMemberIds: string[];
  unavailableMemberIds: string[];
  conditionsMet: string[];
  conflicts: string[];
  reason: string | null;
}

export interface RecommendationResponse {
  candidates: Candidate[];
  excludedRooms: { roomId: string; roomName: string; reasons: string[] }[];
  excludedWindows: Record<string, number>;
  reasonsSource: 'ai' | 'partial' | 'fallback' | 'none';
  timePreferenceApplied: boolean;
}

export interface Assignment {
  id: number;
  title: string | null;
  finalDeadline: string | null;
  deadlineSource: 'user' | 'ai' | null;
  deadlineStatus: 'ok' | 'missing' | 'past';
  deliverableType: string;
  milestones: { name: string; date: string | null }[];
  stages: {
    position: number;
    name: string;
    purpose: string;
    priority: 'must' | 'optional';
    windowStart: string | null;
    windowEnd: string | null;
    anchoredTo: string | null;
    dropped: boolean;
  }[];
}

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) { super(message); }
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '요청을 처리하지 못했어요.';
}

function detailMessage(payload: unknown): string | undefined {
  if (typeof payload !== 'object' || !payload || !('detail' in payload)) return;
  if (typeof payload.detail === 'string') return payload.detail;
  if (Array.isArray(payload.detail)) return '입력한 값과 날짜 범위를 확인해 주세요.';
}

type RequestOptions = { method?: string; body?: object; signal?: AbortSignal };
type MemberInput = { name?: string; busy?: SlotKey[] };
const segment = encodeURIComponent;

export function createApi(baseUrl: string) {
  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    if (!/^https?:\/\//i.test(baseUrl)) throw new ApiError('EXPO_PUBLIC_API_URL에 http 또는 https 서버 주소를 설정해 주세요.');
    const controller = new AbortController();
    const abort = () => controller.abort();
    options.signal?.addEventListener('abort', abort, { once: true });
    if (options.signal?.aborted) abort();
    const timeout = setTimeout(abort, path.endsWith('/conditions') || options.method === 'POST' && /\/(recommendations|assignments)$/.test(path) ? 110_000 : 15_000);
    try {
      const response = await fetch(baseUrl.replace(/\/+$/, '') + '/api' + path, {
        method: options.method ?? 'GET',
        headers: options.body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      });
      if (response.status === 204) return undefined as T;
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new ApiError(detailMessage(payload) ?? `서버 요청에 실패했어요. (HTTP ${response.status})`, response.status);
      if (payload === null) throw new ApiError('서버 응답 형식을 읽을 수 없어요.');
      return payload as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (options.signal?.aborted) throw error;
      if (controller.signal.aborted) throw new ApiError('응답 시간이 길어 요청을 종료했어요. 결과를 확인한 뒤 다시 시도해 주세요.');
      throw new ApiError('TeamPlus 서버에 연결할 수 없어요. 서버 실행 상태와 네트워크를 확인해 주세요.');
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener('abort', abort);
    }
  }

  const group = (id: string) => '/groups/' + segment(id);
  const member = (groupId: string, id: string) => group(groupId) + '/members/' + segment(id);
  const assignment = (groupId: string, id: number) => group(groupId) + '/assignments/' + id;
  return {
    groups: (signal?: AbortSignal) => request<Group[]>('/groups', { signal }),
    group: (id: string, signal?: AbortSignal) => request<Group>(group(id), { signal }),
    createGroup: (name: string, memberNames: readonly string[]) => request<Group>('/groups', { method: 'POST', body: { name, memberNames } }),
    renameGroup: (id: string, name: string) => request<Group>(group(id), { method: 'PATCH', body: { name } }),
    deleteGroup: (id: string) => request<void>(group(id), { method: 'DELETE' }),
    addMember: (id: string, name: string) => request<Member>(group(id) + '/members', { method: 'POST', body: { name } }),
    updateMember: (groupId: string, id: string, body: MemberInput) => request<Member>(member(groupId, id), { method: 'PATCH', body }),
    deleteMember: (groupId: string, id: string) => request<void>(member(groupId, id), { method: 'DELETE' }),
    availability: (id: string, signal?: AbortSignal) => request<AvailabilityResponse>(group(id) + '/availability', { signal }),
    places: (signal?: AbortSignal) => request<Place[]>('/places', { signal }),
    place: (id: string, signal?: AbortSignal) => request<Place>('/places/' + segment(id), { signal }),
    rooms: (signal?: AbortSignal) => request<ApiRoom[]>('/rooms', { signal }),
    roomAvailability: (date: string, groupId?: string, signal?: AbortSignal) => {
      const query = new URLSearchParams({ date });
      if (groupId) query.set('groupId', groupId);
      return request<RoomAvailability[]>('/rooms/availability?' + query.toString(), { signal });
    },
    conditions: (id: string, text: string) => request<ConditionsResponse>(group(id) + '/conditions', { method: 'POST', body: { text } }),
    recommendations: (id: string, conditions: Conditions, dateFrom: string, dateTo: string) =>
      request<RecommendationResponse>(group(id) + '/recommendations', { method: 'POST', body: { conditions, dateFrom, dateTo } }),
    assignments: (id: string, signal?: AbortSignal) => request<Assignment[]>(group(id) + '/assignments', { signal }),
    assignment: (groupId: string, id: number, signal?: AbortSignal) => request<Assignment>(assignment(groupId, id), { signal }),
    createAssignment: (id: string, title: string, noticeText: string) =>
      request<Assignment>(group(id) + '/assignments', { method: 'POST', body: { title: title || null, noticeText } }),
    updateDeadline: (groupId: string, id: number, finalDeadline: string) =>
      request<Assignment>(assignment(groupId, id) + '/deadline', { method: 'PUT', body: { finalDeadline } }),
  };
}

const apiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();
export const api = apiUrl ? createApi(apiUrl) : null;
export const usesTestAi = !!api && process.env.EXPO_PUBLIC_TEST_AI === '1';
