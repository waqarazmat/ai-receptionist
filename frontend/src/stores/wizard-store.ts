import { create } from "zustand";

interface WizardStore {
  currentStep: number;
  completedSteps: Set<number>;
  setStep: (step: number) => void;
  setCompletedSteps: (steps: Set<number>) => void;
  reset: () => void;
}

export const useWizardStore = create<WizardStore>((set) => ({
  currentStep: 0,
  completedSteps: new Set(),
  setStep: (step) => set({ currentStep: step }),
  setCompletedSteps: (steps) => set({ completedSteps: steps }),
  reset: () => set({ currentStep: 0, completedSteps: new Set() }),
}));
