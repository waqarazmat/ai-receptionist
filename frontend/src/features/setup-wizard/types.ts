import type { SetupStateResponse } from "../../types/setup-wizard";

export interface StepComponentProps {
  orgId: string;
  setupState: SetupStateResponse;
  onBack?: () => void;
  onNext: () => void;
}
