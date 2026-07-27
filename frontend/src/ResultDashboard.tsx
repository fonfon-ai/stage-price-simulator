import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ActualResultForm from "./ActualResultForm";
import type { ScenarioOut, SimulateResponse } from "./types";

interface Props {
  result: SimulateResponse;
}

const VENUE_FIT_LABEL: Record<ScenarioOut["venue_fit"], string> = {
  too_small: "小さすぎる",
  good: "適切",
  slightly_large: "やや大きい",
  too_large: "大きすぎる",
};

function yen(n: number): string {
  return `${Math.round(n).toLocaleString("ja-JP")}円`;
}

export default function ResultDashboard({ result }: Props) {
  const focusVenue = result.balance_scenario.venue_name;
  const focusCount = result.balance_scenario.num_performances;
  const chartData = result.scenarios
    .filter((s) => s.venue_name === focusVenue && s.num_performances === focusCount)
    .sort((a, b) => a.price - b.price)
    .map((s) => ({
      price: s.price,
      expected_sold: Math.round(s.expected_sold),
      revenue: Math.round(s.revenue),
    }));

  return (
    <div className="step-card">
      <h2>STEP 5: シミュレーション結果</h2>
      <p className="disclaimer">{result.disclaimer}</p>

      <div className="price-summary-grid">
        <div className="price-tile">
          <div className="price-tile-label">推奨価格帯</div>
          <div className="price-tile-value">
            {yen(result.recommended_price_range[0])} 〜 {yen(result.recommended_price_range[1])}
          </div>
        </div>
        <div className="price-tile">
          <div className="price-tile-label">バランス価格</div>
          <div className="price-tile-value">{yen(result.balance_price)}</div>
        </div>
        <div className="price-tile">
          <div className="price-tile-label">満席重視価格</div>
          <div className="price-tile-value">{yen(result.sellout_price)}</div>
        </div>
        <div className="price-tile">
          <div className="price-tile-label">売上重視価格</div>
          <div className="price-tile-value">{yen(result.revenue_price)}</div>
        </div>
        <div className="price-tile">
          <div className="price-tile-label">利益重視価格</div>
          <div className="price-tile-value">{yen(result.profit_price)}</div>
        </div>
      </div>

      <h3>Venue Fit(バランス案: {focusVenue} / {focusCount}回公演)</h3>
      <p className={`venue-fit-badge venue-fit-${result.balance_scenario.venue_fit}`}>
        {VENUE_FIT_LABEL[result.balance_scenario.venue_fit]}
      </p>
      <p>{result.balance_scenario.venue_fit_message}</p>

      <h3>価格と予想動員・売上</h3>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="price" tickFormatter={(v) => `${v}`} />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip formatter={(v: number) => v.toLocaleString("ja-JP")} />
            <Legend />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="expected_sold"
              name="予想動員(枚)"
              stroke="#2563eb"
              dot={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="revenue"
              name="予想売上(円)"
              stroke="#d97706"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h3>シナリオ比較表</h3>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>会場</th>
              <th>価格</th>
              <th>公演回数</th>
              <th>販売可能席</th>
              <th>予想動員</th>
              <th>稼働率</th>
              <th>売上</th>
              <th>利益</th>
              <th>Venue Fit</th>
            </tr>
          </thead>
          <tbody>
            {result.scenarios.map((s, i) => (
              <tr
                key={i}
                className={
                  s === result.balance_scenario ||
                  (s.venue_name === result.balance_scenario.venue_name &&
                    s.price === result.balance_scenario.price &&
                    s.num_performances === result.balance_scenario.num_performances)
                    ? "row-highlight"
                    : undefined
                }
              >
                <td>{s.venue_name}</td>
                <td>{yen(s.price)}</td>
                <td>{s.num_performances}</td>
                <td>{s.available_seats}</td>
                <td>{Math.round(s.expected_sold)}</td>
                <td>{(s.occupancy_rate * 100).toFixed(0)}%</td>
                <td>{yen(s.revenue)}</td>
                <td>{yen(s.profit)}</td>
                <td>{VENUE_FIT_LABEL[s.venue_fit]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>なぜこの結果になったか</h3>
      <ul className="explanation-list">
        {result.explanation.map((e, i) => (
          <li key={i}>{e.description}</li>
        ))}
      </ul>

      {import.meta.env.VITE_HAS_BACKEND !== "false" && (
        <ActualResultForm
          runId={result.run_id}
          defaultVenueName={result.balance_scenario.venue_name}
          defaultCapacity={
            result.balance_scenario.available_seats / result.balance_scenario.num_performances
          }
          defaultPrice={result.balance_scenario.price}
          defaultNumPerformances={result.balance_scenario.num_performances}
        />
      )}
    </div>
  );
}
