import { ComponentType } from 'react';
import SummaryCard from './SummaryCard';
import CompareCard from './CompareCard';
import RecommendCard from './RecommendCard';
import RiskCard from './RiskCard';
import SimulationCard from './SimulationCard';

export const CARD_REGISTRY: Record<string, ComponentType<{ data: any }>> = {
  summary: SummaryCard,
  compare: CompareCard,
  recommend: RecommendCard,
  risk: RiskCard,
  simulation: SimulationCard,
};
