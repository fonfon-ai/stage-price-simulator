import { useState } from "react";
import { ApiError, submitActualResult } from "./api";
import type { ActualResultInput } from "./types";

interface Props {
  runId: number;
  defaultVenueName: string;
  defaultCapacity: number;
  defaultPrice: number;
  defaultNumPerformances: number;
}

export default function ActualResultForm({
  runId,
  defaultVenueName,
  defaultCapacity,
  defaultPrice,
  defaultNumPerformances,
}: Props) {
  const [venueName, setVenueName] = useState(defaultVenueName);
  const [capacity, setCapacity] = useState(defaultCapacity);
  const [price, setPrice] = useState(defaultPrice);
  const [numPerformances, setNumPerformances] = useState(defaultNumPerformances);
  const [ticketsSold, setTicketsSold] = useState(0);
  const [soldOut, setSoldOut] = useState(false);
  const [daysBeforeSoldOut, setDaysBeforeSoldOut] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    const payload: ActualResultInput = {
      run_id: runId,
      actual_price: price,
      actual_venue_name: venueName,
      actual_capacity: capacity,
      actual_num_performances: numPerformances,
      actual_tickets_sold: ticketsSold,
      actual_sold_out: soldOut,
      actual_days_before_sold_out: soldOut ? daysBeforeSoldOut : null,
    };
    try {
      await submitActualResult(payload);
      setMessage("実績を登録しました。今後のモデル改善のための学習データとして保存されます。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "予期しないエラーが発生しました。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="step-card">
      <h3>公演終了後の実績登録(任意)</h3>
      <p className="step-hint">
        公演終了後に実際の結果を登録すると、将来のモデル改善のための学習データとして活用できます。
      </p>
      <form onSubmit={handleSubmit}>
        <div className="grid-2">
          <label>
            実際の会場名
            <input value={venueName} onChange={(e) => setVenueName(e.target.value)} required />
          </label>
          <label>
            実際のキャパ
            <input
              type="number"
              min={1}
              value={capacity}
              onChange={(e) => setCapacity(Number(e.target.value))}
            />
          </label>
          <label>
            実際の価格
            <input
              type="number"
              min={1}
              value={price}
              onChange={(e) => setPrice(Number(e.target.value))}
              required
            />
          </label>
          <label>
            実際の公演回数
            <input
              type="number"
              min={1}
              value={numPerformances}
              onChange={(e) => setNumPerformances(Number(e.target.value))}
              required
            />
          </label>
          <label>
            実際の販売枚数
            <input
              type="number"
              min={0}
              value={ticketsSold}
              onChange={(e) => setTicketsSold(Number(e.target.value))}
              required
            />
          </label>
        </div>
        <div className="checkbox-row">
          <label className="checkbox-label">
            <input type="checkbox" checked={soldOut} onChange={(e) => setSoldOut(e.target.checked)} />
            完売した
          </label>
          {soldOut && (
            <label>
              完売まで何日前
              <input
                type="number"
                min={0}
                value={daysBeforeSoldOut ?? 0}
                onChange={(e) => setDaysBeforeSoldOut(Number(e.target.value))}
              />
            </label>
          )}
        </div>
        <button type="submit" className="primary-button" disabled={submitting}>
          {submitting ? "登録中..." : "実績を登録する"}
        </button>
        {message && <p className="success-message">{message}</p>}
        {error && <p className="error-message">{error}</p>}
      </form>
    </div>
  );
}
