import type { ActualResultInput, SimulateRequest, SimulateResponse } from "./types";

export class ApiError extends Error {}

export async function runSimulation(payload: SimulateRequest): Promise<SimulateResponse> {
  const res = await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(`シミュレーションの実行に失敗しました (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function submitActualResult(
  payload: ActualResultInput
): Promise<{ id: number; run_id: number }> {
  const res = await fetch("/api/actual_results", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(`実績の登録に失敗しました (${res.status}): ${detail}`);
  }
  return res.json();
}
