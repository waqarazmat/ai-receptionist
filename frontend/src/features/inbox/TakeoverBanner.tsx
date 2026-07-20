import { UserCheck } from "lucide-react";
import { Button } from "../../components/ui/Button";

export interface TakeoverBannerProps {
  escalationReason?: string | null;
  onTakeOver: () => void;
  isTakingOver: boolean;
}

export function TakeoverBanner({ escalationReason, onTakeOver, isTakingOver }: TakeoverBannerProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-amber-800 dark:text-amber-200">AI is currently handling this conversation</p>
        {escalationReason && <p className="mt-0.5 truncate text-xs text-amber-700 dark:text-amber-300">Reason: {escalationReason}</p>}
      </div>
      <Button size="sm" variant="secondary" isLoading={isTakingOver} onClick={onTakeOver}>
        <UserCheck className="h-4 w-4" />
        Take Over
      </Button>
    </div>
  );
}
