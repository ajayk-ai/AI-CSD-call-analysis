import { useNavigation } from '../../state/navigation';
import type { CallFilters } from '../../services/api';
import './OpenCallsButton.css';

interface OpenCallsButtonProps {
  filters: CallFilters;
  /** Defaults to "Review calls". Keep it short — this sits inline in a table row. */
  label?: string;
}

/**
 * "Show me which calls" — the other half of every ranked number on the
 * dashboard.
 *
 * A count on its own can't be checked. This jumps straight to the Calls tab
 * with the matching filter already applied, so "9 calls complained about
 * follow-up" becomes nine actual transcripts a reviewer can read, not a
 * number to take on faith. Stops the click from also toggling whatever
 * clickable row it sits inside (see ClickableSlice / RankedTable row clicks),
 * since the two are different actions on the same row.
 */
export function OpenCallsButton({ filters, label = 'Review calls' }: OpenCallsButtonProps) {
  const { openCalls } = useNavigation();
  return (
    <button
      type="button"
      className="open-calls-btn"
      onClick={(e) => {
        e.stopPropagation();
        openCalls(filters);
      }}
      title="Open the Calls tab, filtered to exactly these calls"
    >
      🔎 {label}
    </button>
  );
}
