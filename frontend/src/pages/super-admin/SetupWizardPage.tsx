import { useEffect, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import { useOrganization } from "../../api/organizations";
import { useSetupState } from "../../api/setup-wizard";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { WizardStepper } from "../../features/setup-wizard/WizardStepper";
import { ApiKeysStep } from "../../features/setup-wizard/steps/ApiKeysStep";
import { BasicInfoStep } from "../../features/setup-wizard/steps/BasicInfoStep";
import { BookingConfigStep } from "../../features/setup-wizard/steps/BookingConfigStep";
import { ChannelConfigStep } from "../../features/setup-wizard/steps/ChannelConfigStep";
import { KnowledgeBaseStep } from "../../features/setup-wizard/steps/KnowledgeBaseStep";
import { ReviewAndActivateStep } from "../../features/setup-wizard/steps/ReviewAndActivateStep";
import { StaffAccessStep } from "../../features/setup-wizard/steps/StaffAccessStep";
import { SystemPromptsStep } from "../../features/setup-wizard/steps/SystemPromptsStep";
import { WorkingHoursStep } from "../../features/setup-wizard/steps/WorkingHoursStep";
import { useWizardStore } from "../../stores/wizard-store";
import { WIZARD_STEP_KEYS, WIZARD_STEPS } from "../../types/setup-wizard";
import type { StepComponentProps } from "../../features/setup-wizard/types";

const STEP_COMPONENTS: Record<string, (props: StepComponentProps) => ReactNode> = {
  basic_info: BasicInfoStep,
  working_hours: WorkingHoursStep,
  channels: ChannelConfigStep,
  api_keys: ApiKeysStep,
  knowledge_base: KnowledgeBaseStep,
  booking: BookingConfigStep,
  system_prompts: SystemPromptsStep,
  staff: StaffAccessStep,
  review: ReviewAndActivateStep,
};

export default function SetupWizardPage() {
  const { orgId = "" } = useParams();
  const navigate = useNavigate();
  const { data: org } = useOrganization(orgId);
  const { data: setupState, isLoading } = useSetupState(orgId);

  const currentStep = useWizardStore((s) => s.currentStep);
  const completedSteps = useWizardStore((s) => s.completedSteps);
  const setStep = useWizardStore((s) => s.setStep);
  const setCompletedSteps = useWizardStore((s) => s.setCompletedSteps);
  const reset = useWizardStore((s) => s.reset);

  useEffect(() => {
    reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  useEffect(() => {
    if (!setupState) return;
    const completed = new Set<number>();
    WIZARD_STEP_KEYS.forEach((key, index) => {
      if (setupState.setup_progress[key]) completed.add(index);
    });
    if (setupState.setup_completed) completed.add(WIZARD_STEPS.length - 1);
    setCompletedSteps(completed);
  }, [setupState, setCompletedSteps]);

  if (isLoading || !setupState) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  const activeStepDef = WIZARD_STEPS[currentStep];
  const StepComponent = STEP_COMPONENTS[activeStepDef.key];

  const goToNext = () => {
    setCompletedSteps(new Set(completedSteps).add(currentStep));
    setStep(Math.min(currentStep + 1, WIZARD_STEPS.length - 1));
  };
  const goBack = () => setStep(Math.max(currentStep - 1, 0));

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{org?.name ?? "Organization Setup"}</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Complete every step to bring this organization online.</p>
        </div>
        <Button variant="secondary" onClick={() => navigate(`/admin/organizations/${orgId}/test`)}>
          <FlaskConical className="h-4 w-4" />
          Test Channels
        </Button>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[260px_1fr] items-start">
        <div className="lg:sticky lg:top-6">
          <WizardStepper
            steps={WIZARD_STEPS}
            currentStep={currentStep}
            completedSteps={completedSteps}
            onStepClick={setStep}
          />
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm min-h-120">
          <StepComponent
            orgId={orgId}
            setupState={setupState}
            onBack={currentStep > 0 ? goBack : undefined}
            onNext={goToNext}
          />
        </div>
      </div>
    </div>
  );
}
