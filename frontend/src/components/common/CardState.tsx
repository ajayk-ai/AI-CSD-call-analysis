import './CardState.css';

interface CardStateProps {
  kind: 'loading' | 'error' | 'empty';
  message?: string;
  /** Shown under an empty state to say what would fill it. */
  hint?: string;
}

/**
 * Placeholder body for a card with nothing to draw yet.
 *
 * "Empty" is a first-class state here rather than a zeroed-out chart: on a
 * fresh database every panel is empty, and a donut of zeros reads as real
 * measurement rather than as "no data yet".
 */
export function CardState({ kind, message, hint }: CardStateProps) {
  if (kind === 'loading') {
    return (
      <div className="card-state" role="status">
        <span className="card-state__spinner" aria-hidden="true" />
        <span className="card-state__text">Loading…</span>
      </div>
    );
  }

  if (kind === 'error') {
    return (
      <div className="card-state card-state--error" role="alert">
        <span className="card-state__icon" aria-hidden="true">
          ⚠️
        </span>
        <span className="card-state__text">{message ?? 'Could not load this panel.'}</span>
      </div>
    );
  }

  return (
    <div className="card-state">
      <span className="card-state__icon" aria-hidden="true">
        📭
      </span>
      <span className="card-state__text">{message ?? 'No data yet'}</span>
      {hint && <span className="card-state__hint">{hint}</span>}
    </div>
  );
}
