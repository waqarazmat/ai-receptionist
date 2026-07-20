export interface WidgetConfig {
  primaryColor: string;
  secondaryColor?: string;        // derived from primaryColor if absent
  position: "bottom-right" | "bottom-left";
  launcherIcon: string;
  headerTitle: string;
  avatarUrl: string | null;
  poweredByVisible: boolean;
  greetingByLang: Record<string, string>;
  responseTimeText?: string;
  businessHoursBehavior: string;
  preChatFormEnabled: boolean;
  preChatFields: Array<{ field: string; required: boolean }>;
  suggestedQuestions?: string[];
}

declare const __API_BASE__: string;
export const API_BASE: string = __API_BASE__;
