import { useRef, type KeyboardEvent } from 'react';
import './SectionNav.css';

export type DashboardSection =
  | 'overview'
  | 'customers'
  | 'quality'
  | 'issues'
  | 'compliance'
  | 'agents';

const SECTIONS: { key: DashboardSection; label: string; icon: string; hint: string }[] = [
  { key: 'customers', label: 'Customers', icon: '😊', hint: 'Sentiment, satisfaction and trend' },
  { key: 'quality', label: 'Call Quality', icon: '🎧', hint: 'Recording clarity and connection' },
  { key: 'issues', label: 'Issues', icon: '⚠️', hint: 'Complaint drivers and machine issues' },
  { key: 'compliance', label: 'Compliance', icon: '📋', hint: 'Script compliance and where it slips' },
  { key: 'agents', label: 'Agents', icon: '👤', hint: 'Performance per agent' },
  { key: 'overview', label: 'Key Insight', icon: '💡', hint: 'Executive summary and cross-signal insights' },
];

interface SectionNavProps {
  active: DashboardSection;
  onChange: (section: DashboardSection) => void;
}

export function SectionNav({ active, onChange }: SectionNavProps) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + SECTIONS.length) % SECTIONS.length;
    buttons.current[next]?.focus();
    onChange(SECTIONS[next].key);
  };

  return (
    <div className="section-nav" role="tablist" aria-label="Dashboard sections">
      {SECTIONS.map((section, index) => (
        <button
          key={section.key}
          ref={(el) => {
            buttons.current[index] = el;
          }}
          type="button"
          role="tab"
          aria-selected={active === section.key}
          tabIndex={active === section.key ? 0 : -1}
          title={section.hint}
          className={`section-nav__button ${active === section.key ? 'section-nav__button--active' : ''}`}
          onClick={() => onChange(section.key)}
          onKeyDown={(event) => onKeyDown(event, index)}
        >
          <span aria-hidden="true">{section.icon}</span>
          {section.label}
        </button>
      ))}
    </div>
  );
}
