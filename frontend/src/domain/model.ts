export type ThemeMode = 'light' | 'dark' | 'system';
export type Day = 0 | 1 | 2 | 3 | 4;
export type SlotKey = `${Day}-${number}`;
export interface Member { id: string; name: string; userId?: string; busy: SlotKey[] }
export interface Group { id: string; name: string; ownerId: string; inviteCode: string | null; members: Member[]; updatedAt: string }
export interface Reservation { id: string; groupId: string; groupName: string; roomId: string; date: string; hour: number; status: 'active' | 'cancelled'; createdAt: string }
export interface AppData { version: 1; seedNamesVersion?: 1 | 2; groups: Group[]; reservations: Reservation[]; theme: ThemeMode }
export interface Place { id: string; name: string; category: '교내' | '카페'; location: string; capacity: number; tags: string[]; description: string; note: string; reservable: boolean }
export interface Room { id: string; name: string; capacity: number }
export const NEW_GROUP_MEMBER_NAMES = ['건우', '승균', '휘서'] as const;
export const DAYS = ['월', '화', '수', '목', '금'];
export const PERIODS = ['09:00–10:30', '10:30–12:00', '12:00–13:30', '13:30–15:00', '15:00–16:30', '16:30–18:00'];
// Reservation slots are hourly and independent of the academic timetable.
export const HOURS = Array.from({ length: 10 }, (_, i) => i + 9);
export const ROOMS: Room[] = [{ id: 'J201', name: '201호', capacity: 4 }, { id: 'J202', name: '202호', capacity: 4 }, { id: 'J301', name: '301호', capacity: 6 }, { id: 'J302', name: '302호', capacity: 8 }];
export function uid() { return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`; }
export function localDate(date = new Date()) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
export function dateAt(offset: number) { const d = new Date(); d.setDate(d.getDate() + offset); return localDate(d); }
export function hourLabel(hour: number) { return `${String(hour).padStart(2, '0')}:00–${String(hour + 1).padStart(2, '0')}:00`; }
