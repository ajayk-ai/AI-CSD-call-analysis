import './TabNav.css';

export type TabKey = 'dashboard' | 'calls' | 'admin';

interface TabNavProps {
  active: TabKey;
  onChange: (tab: TabKey) => void;
}

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'dashboard', label: 'Dashboard', icon: '📊' },
  { key: 'calls', label: 'Calls', icon: '📞' },
  { key: 'admin', label: 'Admin', icon: '🛠️' },
];

export function TabNav({ active, onChange }: TabNavProps) {
  return (
    <nav className="tab-nav" role="tablist" aria-label="Sections">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={active === tab.key}
          className={`tab-nav__tab ${active === tab.key ? 'tab-nav__tab--active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          <span aria-hidden="true">{tab.icon}</span> {tab.label}
        </button>
      ))}
    </nav>
  );
}
