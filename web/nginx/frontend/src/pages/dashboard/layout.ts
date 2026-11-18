// 관제 대시보드 배치표.
// 화면은 1920×1080 고정이고, 머리줄 아래를 24칸 × 12줄 격자로 나눈다.
// 패널을 옮기거나 크기를 바꿀 때는 이 표의 숫자만 고친다. 새 패널은 panels.tsx 의 PANELS 에 등록한 뒤 여기에 한 줄을 더한다.
//
//   col · row = 왼쪽 위 칸(1부터), w · h = 차지하는 칸 수
//
//    1      7              14         18       24
//  1 ┌──────────────── 요약 타일 ────────────────┐
//  3 ├──────┬──────────────┬──────────┬─────────┤
//    │ 로봇  │              │ 카메라    │         │
//  6 ├──────┤    지도       ├──────────┤  경고    │
//    │ 진행  │              │ 점검 지점  │         │
//  9 │ 대기  ├──────────────┴──────────┼─────────┤
//    │ 작업  │ 예정된 점검               │ 이벤트   │
// 12 └──────┴─────────────────────────┴─────────┘
export interface Slot { panel: string; col: number; row: number; w: number; h: number }

export const COLS = 24;
export const ROWS = 12;

export const LAYOUT: Slot[] = [
  { panel: 'kpi', col: 1, row: 1, w: 24, h: 2 },
  { panel: 'robots', col: 1, row: 3, w: 6, h: 3 },
  { panel: 'queue', col: 1, row: 6, w: 6, h: 7 },
  { panel: 'map', col: 7, row: 3, w: 7, h: 7 },
  { panel: 'camera', col: 14, row: 3, w: 4, h: 3 },
  { panel: 'points', col: 14, row: 6, w: 4, h: 4 },
  { panel: 'schedules', col: 7, row: 10, w: 11, h: 3 },
  { panel: 'alerts', col: 18, row: 3, w: 7, h: 5 },
  { panel: 'events', col: 18, row: 8, w: 7, h: 5 },
];
