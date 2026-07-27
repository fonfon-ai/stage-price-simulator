/** rule_v0.1: backend/app/calculation/simulator.py の移植。 */
import { estimateDemand } from "./demandEstimator";
import type { DemandFeatures, ScenarioResult } from "./types";
import type { VenueCandidate } from "../types";
import { classifyVenueFit } from "./venueFit";

export function simulate(
  features: DemandFeatures,
  venue: VenueCandidate,
  price: number,
  numPerformances: number
): ScenarioResult {
  const scenarioFeatures: DemandFeatures = {
    group: features.group,
    past_performances: features.past_performances,
    current_production: features.current_production,
    venue,
    price,
    num_performances: numPerformances,
  };
  const estimate = estimateDemand(scenarioFeatures);

  const availableSeats = venue.capacity * numPerformances;
  const expectedSold = Math.min(availableSeats, estimate.total_expected_demand);
  const occupancyRate = availableSeats > 0 ? expectedSold / availableSeats : 0.0;
  const revenue = expectedSold * price;
  const profit = revenue - venue.venue_cost * numPerformances;

  const [venueFit, venueFitMessage] = classifyVenueFit(occupancyRate);

  return {
    venue_name: venue.name,
    price,
    num_performances: numPerformances,
    available_seats: availableSeats,
    expected_demand: estimate.total_expected_demand,
    expected_sold: expectedSold,
    occupancy_rate: occupancyRate,
    revenue,
    profit,
    venue_fit: venueFit,
    venue_fit_message: venueFitMessage,
  };
}
