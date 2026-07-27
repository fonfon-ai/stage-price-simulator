import type { PastPerformance } from "../types";

interface Props {
  value: PastPerformance[];
  onChange: (value: PastPerformance[]) => void;
}

function emptyPerformance(): PastPerformance {
  return {
    name: "",
    performance_date: "",
    prefecture: "",
    area: "",
    venue_name: "",
    capacity: 100,
    price: 3500,
    num_performances: 1,
    tickets_sold: 0,
    sold_out: false,
    days_before_sold_out: null,
    is_new_work: true,
    is_weekend_holiday: false,
    is_evening: false,
  };
}

export default function StepPastPerformances({ value, onChange }: Props) {
  const update = (i: number, patch: Partial<PastPerformance>) => {
    const next = [...value];
    next[i] = { ...next[i], ...patch };
    onChange(next);
  };
  const add = () => onChange([...value, emptyPerformance()]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div className="step-card">
      <h2>STEP 2: 過去公演</h2>
      <p className="step-hint">
        最低1公演、できれば3〜5公演分登録してください。直近の公演ほど基礎集客力の推定に強く反映されます。
      </p>
      {value.map((p, i) => (
        <div className="performance-card" key={i}>
          <div className="performance-card-header">
            <strong>過去公演 {i + 1}</strong>
            {value.length > 1 && (
              <button type="button" className="link-button" onClick={() => remove(i)}>
                削除
              </button>
            )}
          </div>
          <div className="grid-2">
            <label>
              公演名
              <input value={p.name} onChange={(e) => update(i, { name: e.target.value })} />
            </label>
            <label>
              開催日
              <input
                type="date"
                value={p.performance_date}
                onChange={(e) => update(i, { performance_date: e.target.value })}
              />
            </label>
            <label>
              都道府県
              <input value={p.prefecture} onChange={(e) => update(i, { prefecture: e.target.value })} />
            </label>
            <label>
              エリア
              <input value={p.area} onChange={(e) => update(i, { area: e.target.value })} />
            </label>
            <label>
              会場名
              <input value={p.venue_name} onChange={(e) => update(i, { venue_name: e.target.value })} />
            </label>
            <label>
              キャパ
              <input
                type="number"
                min={1}
                value={p.capacity}
                onChange={(e) => update(i, { capacity: Number(e.target.value) })}
              />
            </label>
            <label>
              チケット価格
              <input
                type="number"
                min={1}
                value={p.price}
                onChange={(e) => update(i, { price: Number(e.target.value) })}
              />
            </label>
            <label>
              公演回数
              <input
                type="number"
                min={1}
                value={p.num_performances}
                onChange={(e) => update(i, { num_performances: Number(e.target.value) })}
              />
            </label>
            <label>
              販売枚数
              <input
                type="number"
                min={0}
                value={p.tickets_sold}
                onChange={(e) => update(i, { tickets_sold: Number(e.target.value) })}
              />
            </label>
          </div>
          <div className="checkbox-row">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={p.is_new_work}
                onChange={(e) => update(i, { is_new_work: e.target.checked })}
              />
              新作
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={p.is_weekend_holiday}
                onChange={(e) => update(i, { is_weekend_holiday: e.target.checked })}
              />
              土日祝
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={p.is_evening}
                onChange={(e) => update(i, { is_evening: e.target.checked })}
              />
              夜公演
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={p.sold_out}
                onChange={(e) =>
                  update(i, {
                    sold_out: e.target.checked,
                    days_before_sold_out: e.target.checked ? p.days_before_sold_out ?? 0 : null,
                  })
                }
              />
              完売した
            </label>
            {p.sold_out && (
              <label>
                完売まで何日前
                <input
                  type="number"
                  min={0}
                  value={p.days_before_sold_out ?? 0}
                  onChange={(e) => update(i, { days_before_sold_out: Number(e.target.value) })}
                />
              </label>
            )}
          </div>
        </div>
      ))}
      <button type="button" className="secondary-button" onClick={add}>
        + 過去公演を追加
      </button>
    </div>
  );
}
