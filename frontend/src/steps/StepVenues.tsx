import type { VenueCandidate } from "../types";

interface Props {
  value: VenueCandidate[];
  onChange: (value: VenueCandidate[]) => void;
}

function emptyVenue(): VenueCandidate {
  return {
    name: "",
    area: "",
    capacity: 100,
    venue_cost: 100000,
    walk_minutes: 5,
    location_rating: 3,
    brand_rating: 3,
  };
}

export default function StepVenues({ value, onChange }: Props) {
  const update = (i: number, patch: Partial<VenueCandidate>) => {
    const next = [...value];
    next[i] = { ...next[i], ...patch };
    onChange(next);
  };
  const add = () => onChange([...value, emptyVenue()]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div className="step-card">
      <h2>STEP 4: 候補会場</h2>
      <p className="step-hint">複数の会場を登録して比較できます。</p>
      {value.map((v, i) => (
        <div className="performance-card" key={i}>
          <div className="performance-card-header">
            <strong>候補会場 {i + 1}</strong>
            {value.length > 1 && (
              <button type="button" className="link-button" onClick={() => remove(i)}>
                削除
              </button>
            )}
          </div>
          <div className="grid-2">
            <label>
              会場名
              <input value={v.name} onChange={(e) => update(i, { name: e.target.value })} />
            </label>
            <label>
              地域
              <input value={v.area} onChange={(e) => update(i, { area: e.target.value })} />
            </label>
            <label>
              キャパ
              <input
                type="number"
                min={1}
                value={v.capacity}
                onChange={(e) => update(i, { capacity: Number(e.target.value) })}
              />
            </label>
            <label>
              会場費(円)
              <input
                type="number"
                min={0}
                value={v.venue_cost}
                onChange={(e) => update(i, { venue_cost: Number(e.target.value) })}
              />
            </label>
            <label>
              駅徒歩分数
              <input
                type="number"
                min={0}
                value={v.walk_minutes}
                onChange={(e) => update(i, { walk_minutes: Number(e.target.value) })}
              />
            </label>
            <label>
              立地評価(1-5)
              <input
                type="number"
                min={1}
                max={5}
                value={v.location_rating}
                onChange={(e) => update(i, { location_rating: Number(e.target.value) })}
              />
            </label>
            <label>
              会場ブランド評価(1-5)
              <input
                type="number"
                min={1}
                max={5}
                value={v.brand_rating}
                onChange={(e) => update(i, { brand_rating: Number(e.target.value) })}
              />
            </label>
          </div>
        </div>
      ))}
      <button type="button" className="secondary-button" onClick={add}>
        + 候補会場を追加
      </button>
    </div>
  );
}
