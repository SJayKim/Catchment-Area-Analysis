/**
 * Role 기반 Hero 카피 + starter chip 프리셋
 * intents.yaml 의 intent 프리셋 (summary/comparison/recommendation/risk/simulation) 매핑
 */

export type Role = 'owner' | 'investor' | 'founder';

export const VALID_ROLES: Role[] = ['owner', 'investor', 'founder'];

export function isValidRole(value: unknown): value is Role {
  return typeof value === 'string' && (VALID_ROLES as string[]).includes(value);
}

export interface RoleMeta {
  id: Role;
  icon: string;
  label: string;
  heroLead: string;
  heroSub: string;
  starterChips: string[];
}

export const ROLES: Record<Role, RoleMeta> = {
  owner: {
    id: 'owner',
    icon: '🧑‍🍳',
    label: '소상공인',
    heroLead: '우리 가게 동네, AI가 해석해 드려요',
    heroSub: '유동인구·매출·경쟁 점포를 3초 안에 한 장으로 요약해드립니다.',
    starterChips: [
      '홍대 카페 매출 어때?',
      '우리 동네 유동인구 시간대별로 보여줘',
      '비슷한 상권이랑 비교해줘',
      '이 상권 리스크는 뭐야?',
      '주변 프랜차이즈 비중 알려줘',
    ],
  },
  investor: {
    id: 'investor',
    icon: '🏢',
    label: '투자자',
    heroLead: '상권 데이터로 결정하세요',
    heroSub: '2~3 상권을 한 화면에서 비교하고 유망 업종을 점수화해 드립니다.',
    starterChips: [
      '강남 vs 성수 유동인구 비교',
      '홍대랑 건대입구 매출 비교해줘',
      '이 상권에서 가장 잘 될 업종은?',
      '시간대별 유동인구 히트맵 보여줘',
      '이 지역 안정성 점수는?',
    ],
  },
  founder: {
    id: 'founder',
    icon: '💡',
    label: '창업 준비',
    heroLead: '어디서 뭘 시작할까?',
    heroSub: '예산·업종·지역 조합으로 월 매출 범위를 시뮬레이션해 드립니다.',
    starterChips: [
      '월 5천만원 예산으로 할 만한 업종',
      '홍대에서 카페 열면 월 매출은?',
      '이 지역에서 유망한 업종 추천',
      '신규 점포 생존율이 높은 상권은?',
      '매출 시뮬레이션 해줘',
    ],
  },
};

export const DEFAULT_HERO_LEAD = '서울 1,650개 상권, AI가 읽어드립니다';
export const DEFAULT_HERO_SUB =
  '클릭 한 번이면 해당 상권의 유동인구·매출·업종을 3초 안에 요약해드려요.';

export const DEFAULT_STARTER_CHIPS = [
  '강남역 상권 요약해줘',
  '홍대랑 건대 비교해줘',
  '이 동네 유망 업종 알려줘',
  '매출 시뮬레이션 돌려줘',
];
