export interface CallQualitySlice {
  label: string;
  count: number;
  percentage: number;
  color: string;
}

export type TimeRangeKey = '1d' | '7d' | '1m' | '3m' | 'all';

export interface CallQualitySnapshot {
  totalCalls: number;
  slices: CallQualitySlice[];
}

export type CallQualityByRange = Record<TimeRangeKey, CallQualitySnapshot>;

export interface SentimentSlice {
  label: string;
  emoji: string;
  count: number;
  percentage: number;
  description: string;
  color: string;
}

export interface SentimentSnapshot {
  usableCalls: number;
  slices: SentimentSlice[];
}

export type SentimentByRange = Record<TimeRangeKey, SentimentSnapshot>;

export interface SatisfactionRow {
  band: string;
  tier: string;
  description: string;
  count: number;
  percentage: number;
  color: string;
}

export interface MonthlyAverage {
  month: string;
  avgRating: number;
}

export interface DailyRating {
  day: number;
  rating: number;
}

export interface RankedIssueRow {
  rank: number;
  category: string;
  count: number;
  percentage: number;
  example: string;
  icon: string;
}

export interface DashboardData {
  totalCallsAnalyzed: number;
  usableCalls: number;
  usableCallsPercentage: number;
  callQualityByRange: CallQualityByRange;
  sentimentByRange: SentimentByRange;
  satisfaction: SatisfactionRow[];
  averageRating: number;
  monthlyAverages: MonthlyAverage[];
  dailyRatings: DailyRating[];
  topIssues: RankedIssueRow[];
  topServiceIssues: RankedIssueRow[];
}
