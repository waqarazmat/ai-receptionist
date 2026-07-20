import { useState, type FormEvent } from "react";
import { useSaveBasicInfo } from "../../../api/setup-wizard";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { INDUSTRIES, TIMEZONES } from "../../../lib/constants";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

export function BasicInfoStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const basicInfo = setupState.basic_info;
  const [name, setName] = useState(basicInfo?.name ?? "");
  const [industry, setIndustry] = useState(basicInfo?.industry ?? "");
  const [timezone, setTimezone] = useState(basicInfo?.timezone ?? "");
  const [address, setAddress] = useState(basicInfo?.address ?? "");
  const [phone, setPhone] = useState(basicInfo?.phone ?? "");
  const [email, setEmail] = useState(basicInfo?.email ?? "");

  const saveBasicInfo = useSaveBasicInfo(orgId);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveBasicInfo.mutate(
      { name, industry, timezone, address, phone, email },
      { onSuccess: onNext },
    );
  };

  return (
    <StepCard
      title="Basic Information"
      description="Tell us the essentials about this organization — this shows up across the dashboard and in customer-facing messages."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Organization name" value={name} onChange={(e) => setName(e.target.value)} required />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label="Industry"
            placeholder="Select an industry"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            options={INDUSTRIES.map((i) => ({ value: i, label: i }))}
            required
          />
          <Select
            label="Timezone"
            placeholder="Select a timezone"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            options={TIMEZONES.map((tz) => ({ value: tz, label: tz }))}
            required
          />
        </div>
        <Input label="Address" value={address} onChange={(e) => setAddress(e.target.value)} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input label="Phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <Input
            label="Contact email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <StepFooter onBack={onBack} isSaving={saveBasicInfo.isPending} />
      </form>
    </StepCard>
  );
}
