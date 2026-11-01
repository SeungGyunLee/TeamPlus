import { Day, Group, SlotKey } from './model';
export function availability(group: Group) {
  return Array.from({ length: 30 }, (_, index) => {
    const day = (index % 5) as Day;
    const period = Math.floor(index / 5);
    const key: SlotKey = `${day}-${period}`;
    const available = group.members.filter(m => !m.busy.includes(key));
    const unavailable = group.members.filter(m => m.busy.includes(key));
    return { key, day, period, available, unavailable, count: available.length, total: group.members.length };
  });
}
export function rankedAvailability(group: Group) {
  return availability(group).sort((a, b) => b.count - a.count || a.day - b.day || a.period - b.period);
}
