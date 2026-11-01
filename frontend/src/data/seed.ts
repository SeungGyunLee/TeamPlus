import { AppData, Place } from '../domain/model';
export function initialData(): AppData {
  return { version: 1, seedNamesVersion: 2, theme: 'light', reservations: [], groups: [{ id: 'first-meet', name: '오픈소스 프로젝트', ownerId: 'local-owner', inviteCode: null, updatedAt: '2026-11-01T00:00:00.000Z', members: [
    { id: 'min', name: '민서', busy: ['0-0','0-1','1-2','2-3','3-0','4-4'] },
    { id: 'jun', name: '준호', busy: ['0-0','1-1','1-2','2-4','3-2','4-3'] },
    { id: 'seo', name: '서연', busy: ['0-1','1-2','2-0','3-4','4-0','4-3'] },
  ] }] };
}
// All locations, rooms, capacities and facilities here are illustrative demo data.
export const PLACES: Place[] = [
  { id: 'jiphyeon', name: '집현전', category: '교내', location: '광운대학교 · 교내 학습 공간', capacity: 8, tags: ['그룹 스터디', '화이트보드', '가상 예약'], description: '아이디어를 모으고, 함께 집중하는 시간. 인원에 맞는 작은 스터디룸에서 팀 프로젝트를 이어가세요.', note: '호실·인실·운영시간은 시연용 데이터입니다. 실제 시설 정보 및 예약 정책과 다릅니다.', reservable: true },
  { id: 'reading', name: '중앙도서관 라운지', category: '교내', location: '광운대학교 · 중앙도서관', capacity: 6, tags: ['개방형', '조용한 대화', '콘센트'], description: '수업 사이 짧은 회의와 자료 정리를 위한 개방형 공간입니다. 함께 앉아 다음 할 일을 정리해 보세요.', note: '실제 좌석 현황을 제공하지 않습니다. 위치·수용 인원·시설은 시연용 예시입니다.', reservable: false },
  { id: 'cafe', name: '캠퍼스 커피룸', category: '카페', location: '광운대역 인근 · 가상 장소', capacity: 4, tags: ['자유로운 대화', '음료', '소규모'], description: '편안한 분위기에서 아이디어를 나누는 소규모 모임 공간. 프로젝트의 첫 대화를 시작해 보세요.', note: '실존 업소가 아닌 시연용 장소입니다. 외부 예약·영업시간 조회는 지원하지 않습니다.', reservable: false },
];
