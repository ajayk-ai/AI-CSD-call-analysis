import type { DashboardData } from '../types/dashboard.types';

// NOTE: All figures below are synthetic/sample data generated for UI
// development purposes only. Replace with real analytics once the
// backend pipeline is wired up.

const dailyRatings = [
  7.1, 7.4, 7.8, 6.9, 7.2, 8.1, 7.6, 7.9, 8.3, 7.5, 7.0, 7.7, 8.2, 7.4, 7.8,
  8.4, 7.6, 7.1, 7.9, 8.0, 7.3, 7.8, 8.5, 7.6, 7.2, 7.9, 8.1, 7.7, 8.0, 7.94,
].map((rating, index) => ({ day: index + 1, rating }));

export const dashboardData: DashboardData = {
  totalCallsAnalyzed: 134,
  usableCalls: 112,
  usableCallsPercentage: 83.58,

  callQualityByRange: {
    '1d': {
      totalCalls: 5,
      slices: [
        { label: 'Good Clear Calls', count: 2, percentage: 40.0, color: 'var(--color-good)' },
        { label: 'Partial but Usable Calls', count: 2, percentage: 40.0, color: 'var(--color-warning)' },
        { label: 'Rejected / Corrupted Calls', count: 1, percentage: 20.0, color: 'var(--color-bad)' },
      ],
    },
    '7d': {
      totalCalls: 19,
      slices: [
        { label: 'Good Clear Calls', count: 8, percentage: 42.11, color: 'var(--color-good)' },
        { label: 'Partial but Usable Calls', count: 8, percentage: 42.11, color: 'var(--color-warning)' },
        { label: 'Rejected / Corrupted Calls', count: 3, percentage: 15.79, color: 'var(--color-bad)' },
      ],
    },
    '1m': {
      totalCalls: 54,
      slices: [
        { label: 'Good Clear Calls', count: 24, percentage: 44.44, color: 'var(--color-good)' },
        { label: 'Partial but Usable Calls', count: 21, percentage: 38.89, color: 'var(--color-warning)' },
        { label: 'Rejected / Corrupted Calls', count: 9, percentage: 16.67, color: 'var(--color-bad)' },
      ],
    },
    '3m': {
      totalCalls: 97,
      slices: [
        { label: 'Good Clear Calls', count: 43, percentage: 44.33, color: 'var(--color-good)' },
        { label: 'Partial but Usable Calls', count: 38, percentage: 39.18, color: 'var(--color-warning)' },
        { label: 'Rejected / Corrupted Calls', count: 16, percentage: 16.49, color: 'var(--color-bad)' },
      ],
    },
    all: {
      totalCalls: 134,
      slices: [
        { label: 'Good Clear Calls', count: 59, percentage: 44.03, color: 'var(--color-good)' },
        { label: 'Partial but Usable Calls', count: 53, percentage: 39.55, color: 'var(--color-warning)' },
        { label: 'Rejected / Corrupted Calls', count: 22, percentage: 16.42, color: 'var(--color-bad)' },
      ],
    },
  },

  sentimentByRange: {
    '1d': {
      usableCalls: 4,
      slices: [
        { label: 'POSITIVE', emoji: '🙂', count: 2, percentage: 50.0, description: 'Satisfied with service, technician behavior and dealer support', color: 'var(--color-good)' },
        { label: 'NEUTRAL', emoji: '😐', count: 1, percentage: 25.0, description: 'Mixed experience, some issues but manageable', color: 'var(--color-warning)' },
        { label: 'NEGATIVE', emoji: '☹️', count: 1, percentage: 25.0, description: 'Very dissatisfied mainly due to response time & resolution', color: 'var(--color-bad)' },
      ],
    },
    '7d': {
      usableCalls: 16,
      slices: [
        { label: 'POSITIVE', emoji: '🙂', count: 9, percentage: 56.25, description: 'Satisfied with service, technician behavior and dealer support', color: 'var(--color-good)' },
        { label: 'NEUTRAL', emoji: '😐', count: 5, percentage: 31.25, description: 'Mixed experience, some issues but manageable', color: 'var(--color-warning)' },
        { label: 'NEGATIVE', emoji: '☹️', count: 2, percentage: 12.5, description: 'Very dissatisfied mainly due to response time & resolution', color: 'var(--color-bad)' },
      ],
    },
    '1m': {
      usableCalls: 45,
      slices: [
        { label: 'POSITIVE', emoji: '🙂', count: 27, percentage: 60.0, description: 'Satisfied with service, technician behavior and dealer support', color: 'var(--color-good)' },
        { label: 'NEUTRAL', emoji: '😐', count: 13, percentage: 28.89, description: 'Mixed experience, some issues but manageable', color: 'var(--color-warning)' },
        { label: 'NEGATIVE', emoji: '☹️', count: 5, percentage: 11.11, description: 'Very dissatisfied mainly due to response time & resolution', color: 'var(--color-bad)' },
      ],
    },
    '3m': {
      usableCalls: 81,
      slices: [
        { label: 'POSITIVE', emoji: '🙂', count: 48, percentage: 59.26, description: 'Satisfied with service, technician behavior and dealer support', color: 'var(--color-good)' },
        { label: 'NEUTRAL', emoji: '😐', count: 23, percentage: 28.4, description: 'Mixed experience, some issues but manageable', color: 'var(--color-warning)' },
        { label: 'NEGATIVE', emoji: '☹️', count: 10, percentage: 12.35, description: 'Very dissatisfied mainly due to response time & resolution', color: 'var(--color-bad)' },
      ],
    },
    all: {
      usableCalls: 112,
      slices: [
        { label: 'POSITIVE', emoji: '🙂', count: 66, percentage: 58.93, description: 'Satisfied with service, technician behavior and dealer support', color: 'var(--color-good)' },
        { label: 'NEUTRAL', emoji: '😐', count: 32, percentage: 28.57, description: 'Mixed experience, some issues but manageable', color: 'var(--color-warning)' },
        { label: 'NEGATIVE', emoji: '☹️', count: 14, percentage: 12.5, description: 'Very dissatisfied mainly due to response time & resolution', color: 'var(--color-bad)' },
      ],
    },
  },

  satisfaction: [
    {
      band: '9 - 10',
      tier: 'Excellent (Very Satisfied)',
      description: 'Excellent (Very Satisfied)',
      count: 48,
      percentage: 42.86,
      color: 'var(--color-good)',
    },
    {
      band: '7 - 8',
      tier: 'Good (Satisfied)',
      description: 'Good (Satisfied)',
      count: 36,
      percentage: 32.14,
      color: 'var(--color-good-alt)',
    },
    {
      band: '5 - 6',
      tier: 'Average (Neutral)',
      description: 'Average (Neutral)',
      count: 18,
      percentage: 16.07,
      color: 'var(--color-warning)',
    },
    {
      band: '1 - 4',
      tier: 'Poor (Dissatisfied)',
      description: 'Poor (Dissatisfied)',
      count: 10,
      percentage: 8.93,
      color: 'var(--color-bad)',
    },
  ],

  averageRating: 7.94,

  monthlyAverages: [
    { month: 'MAY AVG', avgRating: 6.84 },
    { month: 'JUN AVG', avgRating: 7.21 },
    { month: 'JUL AVG', avgRating: 7.56 },
  ],

  dailyRatings,

  topIssues: [
    { rank: 1, category: 'Delay in Service Response', count: 35, percentage: 31.25, example: '"Service took too long" / "Took time to respond"', icon: '⏱️' },
    { rank: 2, category: 'Repeat Issue After Service', count: 24, percentage: 21.43, example: '"Still facing same problem" / "Issue not resolved"', icon: '🔁' },
    { rank: 3, category: 'Spare Parts Delay', count: 16, percentage: 14.29, example: '"Parts not available" / "Delayed in getting parts"', icon: '⚙️' },
    { rank: 4, category: 'Poor Follow-up / No Updates', count: 13, percentage: 11.61, example: '"No update given" / "Had to follow up"', icon: '📞' },
    { rank: 5, category: 'Installation / Delivery Issues', count: 8, percentage: 7.14, example: '"Installation delayed" / "Delivery issues"', icon: '🚚' },
    { rank: 6, category: 'Other Issues (AC, Electrical, GPS, etc.)', count: 16, percentage: 14.29, example: '"AC not working" / "GPS issue"', icon: '🛠️' },
  ],

  topServiceIssues: [
    { rank: 1, category: 'Hydraulic Issues', count: 28, percentage: 25.0, example: '"Hydraulic leak" / "Low hydraulic oil"', icon: '🧰' },
    { rank: 2, category: 'Oil Leakage', count: 20, percentage: 17.86, example: '"Oil leak in main hat" / "Leakage in hydraulic line"', icon: '🛢️' },
    { rank: 3, category: 'Transmission Issues', count: 14, percentage: 12.5, example: '"Gear changing issue" / "Transmission noise"', icon: '⚙️' },
    { rank: 4, category: 'AC / Cooling Problems', count: 10, percentage: 8.93, example: '"AC cooling not working" / "AC not cool"', icon: '❄️' },
    { rank: 5, category: 'Electrical / Wiring / GPS Issues', count: 10, percentage: 8.93, example: '"Battery not charging" / "GPS not working"', icon: '🔌' },
    { rank: 6, category: 'Pipe / Hose Leakage / Burst', count: 8, percentage: 7.14, example: '"Pipe leak" / "Hose burst"', icon: '🚿' },
    { rank: 7, category: 'Engine Performance Issues', count: 7, percentage: 6.25, example: '"Engine power low" / "Start problem"', icon: '🏎️' },
    { rank: 8, category: 'Other Mechanical Issues', count: 16, percentage: 14.29, example: '"Clutch issue" / "Other parts failure"', icon: '🔧' },
  ],
};
