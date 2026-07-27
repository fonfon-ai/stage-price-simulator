import type { GroupInfo } from "../types";

interface Props {
  value: GroupInfo;
  onChange: (value: GroupInfo) => void;
}

export default function StepGroup({ value, onChange }: Props) {
  const set = <K extends keyof GroupInfo>(key: K, v: GroupInfo[K]) =>
    onChange({ ...value, [key]: v });

  return (
    <div className="step-card">
      <h2>STEP 1: 団体情報</h2>
      <p className="step-hint">
        SNSフォロワー数は参考情報として使いますが、動員力の判断は主に過去の公演実績から行います。
      </p>
      <label>
        団体名
        <input
          value={value.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="例: 劇団○○"
        />
      </label>
      <label>
        ジャンル
        <select value={value.genre} onChange={(e) => set("genre", e.target.value as GroupInfo["genre"])}>
          <option value="play">演劇</option>
          <option value="conte">コント</option>
          <option value="other">その他</option>
        </select>
      </label>
      <label>
        活動年数
        <input
          type="number"
          min={0}
          value={value.years_active}
          onChange={(e) => set("years_active", Number(e.target.value))}
        />
      </label>
      <div className="grid-2">
        <label>
          Xフォロワー数
          <input
            type="number"
            min={0}
            value={value.sns_x_followers}
            onChange={(e) => set("sns_x_followers", Number(e.target.value))}
          />
        </label>
        <label>
          Instagramフォロワー数
          <input
            type="number"
            min={0}
            value={value.sns_instagram_followers}
            onChange={(e) => set("sns_instagram_followers", Number(e.target.value))}
          />
        </label>
        <label>
          YouTube登録者数
          <input
            type="number"
            min={0}
            value={value.sns_youtube_subscribers}
            onChange={(e) => set("sns_youtube_subscribers", Number(e.target.value))}
          />
        </label>
        <label>
          その他SNSフォロワー数
          <input
            type="number"
            min={0}
            value={value.sns_other_followers}
            onChange={(e) => set("sns_other_followers", Number(e.target.value))}
          />
        </label>
      </div>
    </div>
  );
}
