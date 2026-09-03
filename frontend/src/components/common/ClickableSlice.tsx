import type { ReactNode } from 'react';
import './ClickableSlice.css';

interface ClickableSliceProps {
  /** True when this slice is the dashboard's current selection for its dimension. */
  active: boolean;
  onClick: () => void;
  /** What clicking does, in words — this is the only place the interaction is
   *  explained, so it's written for an end user, not for us. */
  title: string;
  children: ReactNode;
}

/**
 * One clickable row of a KPI card's legend or table.
 *
 * Every KPI card that participates in cross-filtering wraps its rows in this,
 * so "click a slice to filter the dashboard by it, click it again to clear"
 * looks and behaves identically everywhere rather than being re-invented per
 * card. The button is transparent by design: it adds an affordance to the
 * existing row rather than replacing its layout.
 */
export function ClickableSlice({ active, onClick, title, children }: ClickableSliceProps) {
  return (
    <button
      type="button"
      className={`slice-toggle ${active ? 'slice-toggle--active' : ''}`}
      onClick={onClick}
      title={title}
      aria-pressed={active}
    >
      {children}
    </button>
  );
}

/** The tooltip every clickable slice shows — one wording, one place. */
export function sliceTitle(active: boolean, label: string): string {
  return active
    ? `Clear this filter and show all calls again`
    : `Filter the whole dashboard to ${label}`;
}
