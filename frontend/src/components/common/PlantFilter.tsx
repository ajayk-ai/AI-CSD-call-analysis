import './PlantFilter.css';

interface PlantFilterProps {
  /** Plant codes to offer (e.g. ["CE", "TA"]) — dynamic, not hardcoded, so a
   *  third plant that shows up in the data gets a button without a code change. */
  plants: string[];
  value: string | null;
  onChange: (plant: string | null) => void;
}

/**
 * Global plant filter — one selection shared by every card on the page,
 * unlike the per-card TimeRangeFilter. Plant codes come from the backend
 * (the last two letters of the recording's team code, e.g. "BMCSTCE" -> "CE"),
 * so this renders nothing until at least one is known.
 */
export function PlantFilter({ plants, value, onChange }: PlantFilterProps) {
  if (plants.length === 0) return null;

  return (
    <div className="plant-filter" role="tablist" aria-label="Plant">
      <span className="plant-filter__label">Plant</span>
      <button
        type="button"
        role="tab"
        aria-selected={value === null}
        className={`plant-filter__btn ${value === null ? 'plant-filter__btn--active' : ''}`}
        onClick={() => onChange(null)}
      >
        All
      </button>
      {plants.map((plant) => (
        <button
          key={plant}
          type="button"
          role="tab"
          aria-selected={value === plant}
          className={`plant-filter__btn ${value === plant ? 'plant-filter__btn--active' : ''}`}
          onClick={() => onChange(plant)}
        >
          {plant}
        </button>
      ))}
    </div>
  );
}
