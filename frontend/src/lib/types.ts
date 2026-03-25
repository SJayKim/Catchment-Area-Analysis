export interface District {
  code: string;
  name: string;
  type: '골목상권' | '발달상권' | '전통시장' | string;
  center: { lat: number; lng: number };
  polygon?: number[][];
  dataQuarter?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  type?: 'text' | 'card' | 'error';
  cardType?: string;
  cardData?: SummaryCardData | CompareCardData | RecommendCardData | RiskCardData | Record<string, unknown>;
  timestamp: Date;
}

export interface SummaryCardData {
  districtName: string;
  districtType: string;
  summary: string;
  floatingPopulation: {
    dailyAvg: number;
    peakHour: number;
    byHour: { hour: number; pop: number }[];
  };
  topCategories: { name: string; count: number }[];
  status: 'growing' | 'stable' | 'declining';
  closeRate: { current: number; average: number };
  dataQuarter: string;
}

export interface CompareCardData {
  districts: Record<string, {
    district_code: string;
    floating_pop: number;
    main_age: string;
    store_count: number;
    monthly_sales: number;
    close_rate: number;
    status: 'growing' | 'stable' | 'declining';
    quarter?: string;
    error?: string;
  }>;
  district_codes: string[];
  districtNames?: Record<string, string>;
  aiSummary?: string;
}

export interface RecommendCardData {
  district_code: string;
  quarter: string;
  recommendations: {
    rank: number;
    category_name: string;
    category_code: string;
    score: number;
    per_store_sales: number;
    store_count: number;
    close_rate: number;
    age_match: number;
    monthly_sales: number;
    reasons: string[];
    startup_cost?: number;
  }[];
  total_categories_analyzed: number;
  message?: string;
  districtName?: string;
}

export interface RiskCardData {
  district_code: string;
  stability: {
    score: number | null;
    grade: string;
    trend?: { direction: string; detail: string };
    quarters_analyzed: number;
    message?: string;
  };
  survival_by_category: {
    category: string;
    avg_months: number;
    sample_count: number;
  }[];
  risk_categories: {
    category: string;
    close_rate: number;
    warning: string;
  }[];
  quarterly_trend: {
    quarter: string;
    store_count: number;
    open: number;
    close: number;
  }[];
  districtName?: string;
}

export interface SSEEvent {
  type: 'thinking' | 'tool' | 'text' | 'card' | 'map_cmd' | 'suggestion' | 'done' | 'error';
  [key: string]: unknown;
}

export interface MapBounds {
  sw_lat: number;
  sw_lng: number;
  ne_lat: number;
  ne_lng: number;
}

export interface PolygonFeature {
  code: string;
  name: string;
  type: string;
  coordinates: number[][];
  center: { lat: number; lng: number };
}
