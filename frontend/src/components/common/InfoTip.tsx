import './InfoTip.css';

interface InfoTipProps {
  text: string;
}

/** A small "ⓘ" affordance that reveals an explanation on hover/focus — for
 *  the handful of labels ("Usable Calls", "AI Estimated") that mean something
 *  precise but aren't self-explanatory to a first-time reader. CSS-only
 *  (no portal/positioning library): the tooltip is an absolutely positioned
 *  child shown via :hover/:focus-visible, which is enough at this scale. */
export function InfoTip({ text }: InfoTipProps) {
  return (
    <span className="info-tip" tabIndex={0}>
      <span className="info-tip__icon" aria-hidden="true">
        i
      </span>
      <span className="info-tip__bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}
