import { useState } from "react";
import { ApiError, runSimulation } from "./api";
import ResultDashboard from "./ResultDashboard";
import StepCurrentProduction from "./steps/StepCurrentProduction";
import StepGroup from "./steps/StepGroup";
import StepPastPerformances from "./steps/StepPastPerformances";
import StepVenues from "./steps/StepVenues";
import type {
  CurrentProduction,
  GroupInfo,
  PastPerformance,
  SimulateResponse,
  VenueCandidate,
} from "./types";

const STEP_TITLES = ["団体情報", "過去公演", "今回の公演", "候補会場", "結果"];

function initialGroup(): GroupInfo {
  return {
    name: "",
    genre: "play",
    years_active: 1,
    sns_x_followers: 0,
    sns_instagram_followers: 0,
    sns_youtube_subscribers: 0,
    sns_other_followers: 0,
  };
}

function initialPastPerformances(): PastPerformance[] {
  return [
    {
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
    },
  ];
}

function initialCurrentProduction(): CurrentProduction {
  return {
    area: "",
    performance_date: null,
    is_new_work: true,
    is_weekend_holiday: true,
    is_evening: false,
    rarity_level: "mid",
    has_guest: false,
    is_special: false,
    price_min: 3000,
    price_max: 4500,
  };
}

function initialVenues(): VenueCandidate[] {
  return [
    {
      name: "",
      area: "",
      capacity: 150,
      venue_cost: 150000,
      walk_minutes: 5,
      location_rating: 3,
      brand_rating: 3,
    },
  ];
}

export default function App() {
  const [step, setStep] = useState(0);
  const [group, setGroup] = useState<GroupInfo>(initialGroup());
  const [pastPerformances, setPastPerformances] = useState<PastPerformance[]>(
    initialPastPerformances()
  );
  const [currentProduction, setCurrentProduction] = useState<CurrentProduction>(
    initialCurrentProduction()
  );
  const [numPerformancesCandidates, setNumPerformancesCandidates] = useState<number[]>([1, 2]);
  const [venues, setVenues] = useState<VenueCandidate[]>(initialVenues());
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canProceedFromStep = (s: number): boolean => {
    if (s === 0) return group.name.trim().length > 0;
    if (s === 1)
      return pastPerformances.every(
        (p) => p.name.trim().length > 0 && p.performance_date.length > 0 && p.capacity > 0
      );
    if (s === 2) return currentProduction.price_min > 0 && currentProduction.price_max > 0;
    if (s === 3) return venues.every((v) => v.name.trim().length > 0 && v.capacity > 0);
    return true;
  };

  const goNext = async () => {
    if (step === 3) {
      setLoading(true);
      setError(null);
      try {
        const response = await runSimulation({
          group,
          past_performances: pastPerformances,
          current_production: currentProduction,
          venues,
          num_performances_candidates: numPerformancesCandidates,
        });
        setResult(response);
        setStep(4);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "予期しないエラーが発生しました。");
      } finally {
        setLoading(false);
      }
      return;
    }
    setStep((s) => Math.min(s + 1, STEP_TITLES.length - 1));
  };

  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>この公演、いくらで・どこで・何席売る？</h1>
        <p className="app-subtitle">
          演劇・コントの主催者が、価格・会場・公演回数のトレードオフを比較検討するための意思決定支援ツール
        </p>
      </header>

      <ol className="step-indicator">
        {STEP_TITLES.map((title, i) => (
          <li key={title} className={i === step ? "step-active" : i < step ? "step-done" : ""}>
            {i + 1}. {title}
          </li>
        ))}
      </ol>

      {step === 0 && <StepGroup value={group} onChange={setGroup} />}
      {step === 1 && (
        <StepPastPerformances value={pastPerformances} onChange={setPastPerformances} />
      )}
      {step === 2 && (
        <StepCurrentProduction
          value={currentProduction}
          onChange={setCurrentProduction}
          numPerformancesCandidates={numPerformancesCandidates}
          onChangeCandidates={setNumPerformancesCandidates}
        />
      )}
      {step === 3 && <StepVenues value={venues} onChange={setVenues} />}
      {step === 4 && result && <ResultDashboard result={result} />}

      {error && <p className="error-message">{error}</p>}

      {step < 4 && (
        <div className="wizard-nav">
          <button type="button" onClick={goBack} disabled={step === 0} className="secondary-button">
            戻る
          </button>
          <button
            type="button"
            onClick={goNext}
            disabled={!canProceedFromStep(step) || loading}
            className="primary-button"
          >
            {step === 3 ? (loading ? "計算中..." : "シミュレーション実行") : "次へ"}
          </button>
        </div>
      )}
      {step === 4 && (
        <div className="wizard-nav">
          <button type="button" onClick={() => setStep(3)} className="secondary-button">
            条件を変更する
          </button>
        </div>
      )}
    </div>
  );
}
