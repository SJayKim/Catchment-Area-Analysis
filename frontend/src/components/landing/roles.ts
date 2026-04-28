/**
 * Role 기반 Hero 카피 + starter chip 프리셋
 * intents.yaml 의 intent 프리셋 (summary/comparison/recommendation/risk/simulation) 매핑
 */

import { LineChart, Sparkle, Store, type LucideIcon } from 'lucide-react';

export type Role = 'owner' | 'investor' | 'founder';

export const VALID_ROLES: Role[] = ['owner', 'investor', 'founder'];

export function isValidRole(value: unknown): value is Role {
  return typeof value === 'string' && (VALID_ROLES as string[]).includes(value);
}

export interface RoleMeta {
  id: Role;
  Icon: LucideIcon;
  label: string;
  heroLead: string;
  heroSub: string;
  starterChips: string[];
}

export const ROLES: Record<Role, RoleMeta> = {
  owner: {
    id: 'owner',
    Icon: Store,
    label: '소상공인',
    heroLead: '우리 동네 상권, 숫자로 이해하기',
    heroSub: '유동인구·매출·경쟁 점포를 한 장으로 정리해 드립니다.',
    starterChips: [
      '홍대 카페 매출 추이',
      '시간대별 유동인구',
      '인근 유사 상권 비교',
      '이 상권의 주요 리스크',
      '프랜차이즈 비중',
    ],
  },
  investor: {
    id: 'investor',
    Icon: LineChart,
    label: '투자자',
    heroLead: '데이터로 의사결정하는 상권 탐색',
    heroSub: '2~3 상권을 나란히 비교하고 유망 업종을 점수로 확인합니다.',
    starterChips: [
      '강남 vs 성수 유동인구',
      '홍대 vs 건대입구 매출',
      '최고 기대 업종 Top 5',
      '시간대별 히트맵',
      '상권 안정성 점수',
    ],
  },
  founder: {
    id: 'founder',
    Icon: Sparkle,
    label: '창업 준비',
    heroLead: '어디서 시작할지, 수치로 고르기',
    heroSub: '예산·업종·지역 조합으로 월 매출 범위를 시뮬레이션합니다.',
    starterChips: [
      '예산 5천만원 창업 후보',
      '홍대 카페 월 매출 추정',
      '유망 업종 추천',
      '신규 점포 생존율 상위',
      '매출 시뮬레이션',
    ],
  },
};

export const DEFAULT_HERO_LEAD = '서울 1,650개 상권, 데이터로 읽다';
export const DEFAULT_HERO_SUB =
  '지도 위 상권을 선택하면 유동인구·매출·업종 구성을 한 장의 리포트로 확인합니다.';

export const DEFAULT_STARTER_CHIPS = [
  '강남역 상권 요약',
  '홍대 vs 건대 비교',
  '유망 업종 Top 5',
  '월 매출 시뮬레이션',
];
