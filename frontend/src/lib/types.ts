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
  cardData?: SummaryCardData | CompareCardData | RecommendCardData | RiskCardData | SimulationCardData | Record<string, unknown>;
  timestamp: Date;
}

export interface DataSourceInfo {
  id: string;
  name: string;
  organization: string;
  platform: string;
  api_endpoint: string;
  url: string;
  license: string;
  collection_method: string;
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
  dataSources?: DataSourceInfo[];
}

export interface CompareCardData {
  districts: Record<string, {
    district_code: string;
    district_name?: string;
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
  dataSources?: DataSourceInfo[];
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
  dataSources?: DataSourceInfo[];
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
  dataSources?: DataSourceInfo[];
}

export interface SimulationCardData {
  district_code: string;
  category_code: string;
  category_name: string;
  quarter: string;
  simulation: {
    low: number;
    avg: number;
    high: number;
  };
  basis: {
    total_monthly_sales: number;
    store_count: number;
    additional_competitors: number;
    effective_stores: number;
    unit_price: number | null;
    default_unit_price: number | null;
    price_ratio: number;
  };
  percentiles: {
    p25_ratio: number;
    p75_ratio: number;
    sample_count: number;
    reliable: boolean;
  };
  seoul_comparison: {
    seoul_avg: number;
    diff_percent: number;
    label: string;
  } | null;
  disclaimer: string;
  districtName?: string;
  dataSources?: DataSourceInfo[];
}

export type AgentStepStatus = 'pending' | 'in_progress' | 'completed';

export interface AgentStep {
  id: string;
  label: string;
  status: AgentStepStatus;
  toolName?: string;
}

export type SSEEvent =
  | { type: 'thinking'; step?: string; icon?: string }
  | { type: 'plan'; intent?: string; steps?: string[] }
  | { type: 'tool'; name: string; input?: Record<string, unknown>; icon?: string; progress_label?: string }
  | { type: 'tool_end'; name: string; icon?: string; done_label?: string }
  | { type: 'text'; content: string }
  | { type: 'card'; card_type: string; data: Record<string, unknown> }
  | { type: 'map_cmd'; action: string; params?: Record<string, unknown>; district_code?: string; district_name?: string; district_type?: string }
  | { type: 'suggestion'; questions: string[] }
  | { type: 'done'; trace_id?: string }
  | { type: 'error'; message?: string };

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
