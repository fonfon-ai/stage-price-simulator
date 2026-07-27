import type { CurrentProduction } from "../types";

interface Props {
  value: CurrentProduction;
  onChange: (value: CurrentProduction) => void;
  numPerformancesCandidates: number[];
  onChangeCandidates: (value: number[]) => void;
}

export default function StepCurrentProduction({
  value,
  onChange,
  numPerformancesCandidates,
  onChangeCandidates,
}: Props) {
  const set = <K extends keyof CurrentProduction>(key: K, v: CurrentProduction[K]) =>
    onChange({ ...value, [key]: v });

  const candidatesText = numPerformancesCandidates.join(", ");

  return (
    <div className="step-card">
      <h2>STEP 3: 今回の公演</h2>
      <div className="grid-2">
        <label>
          開催地域
          <input value={value.area} onChange={(e) => set("area", e.target.value)} />
        </label>
        <label>
          公演日
          <input
            type="date"
            value={value.performance_date ?? ""}
            onChange={(e) => set("performance_date", e.target.value || null)}
          />
        </label>
        <label>
          希少性
          <select
            value={value.rarity_level}
            onChange={(e) => set("rarity_level", e.target.value as CurrentProduction["rarity_level"])}
          >
            <option value="low">低い</option>
            <option value="mid">普通</option>
            <option value="high">高い(滅多にやらない)</option>
          </select>
        </label>
        <label>
          希望価格下限(円)
          <input
            type="number"
            min={1}
            value={value.price_min}
            onChange={(e) => set("price_min", Number(e.target.value))}
          />
        </label>
        <label>
          希望価格上限(円)
          <input
            type="number"
            min={1}
            value={value.price_max}
            onChange={(e) => set("price_max", Number(e.target.value))}
          />
        </label>
        <label>
          公演回数候補(カンマ区切り 例: 1, 2, 3)
          <input
            value={candidatesText}
            onChange={(e) =>
              onChangeCandidates(
                e.target.value
                  .split(",")
                  .map((s) => Number(s.trim()))
                  .filter((n) => Number.isFinite(n) && n > 0)
              )
            }
          />
        </label>
      </div>
      <div className="checkbox-row">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={value.is_new_work}
            onChange={(e) => set("is_new_work", e.target.checked)}
          />
          新作
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={value.is_weekend_holiday}
            onChange={(e) => set("is_weekend_holiday", e.target.checked)}
          />
          土日祝
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={value.is_evening}
            onChange={(e) => set("is_evening", e.target.checked)}
          />
          夜公演
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={value.has_guest}
            onChange={(e) => set("has_guest", e.target.checked)}
          />
          ゲスト有り
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={value.is_special}
            onChange={(e) => set("is_special", e.target.checked)}
          />
          特別公演
        </label>
      </div>
    </div>
  );
}
