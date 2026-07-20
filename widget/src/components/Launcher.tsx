import type { WidgetConfig } from "../types.js";

interface Props {
  config: WidgetConfig;
  isOpen: boolean;
  onClick: () => void;
}

export function Launcher({ config, onClick }: Props) {
  const posClass = config.position === "bottom-left" ? "pos-left" : "pos-right";
  return (
    <button
      class={`launcher ${posClass}`}
      onClick={onClick}
      aria-label="Open chat"
      type="button"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  );
}
