import { render } from "preact";
import { h } from "preact";
import { App } from "./app.js";
import { STYLES } from "./styles.js";
import { fetchConfig } from "./api.js";
import type { WidgetConfig } from "./types.js";

declare const __API_BASE__: string;

// Double-injection guard
if (!(window as unknown as Record<string, unknown>)["__platformWidgetLoaded"]) {
  (window as unknown as Record<string, unknown>)["__platformWidgetLoaded"] = true;

  // Capture currentScript synchronously at IIFE evaluation time.
  // document.currentScript is null for async/defer scripts — fall back to attribute query.
  const scriptEl =
    (document.currentScript as HTMLScriptElement | null) ??
    (document.querySelector("script[data-org-id]") as HTMLScriptElement | null);

  const orgId    = scriptEl?.dataset["orgId"] ?? "";
  const apiBase  = scriptEl?.dataset["apiBase"] ?? (typeof __API_BASE__ !== "undefined" ? __API_BASE__ : "http://localhost:8000");

  if (!orgId) {
    console.warn("[GenAI Widget] Missing data-org-id attribute on <script> tag.");
  } else {
    // Fetch config BEFORE mounting — widget stays invisible until colors are known.
    // This eliminates any flash of default/wrong colors on first render.
    fetchConfig(orgId, apiBase)
      .then((config: WidgetConfig) => {
        // Create host element (outside DOM flow, pointer-events forwarded to shadow)
        const host = document.createElement("div");
        host.id = "platform-widget-root";
        host.style.cssText = "position:fixed;z-index:2147483647;top:0;left:0;width:0;height:0;overflow:visible;pointer-events:none";
        document.body.appendChild(host);

        // Shadow DOM — full CSS isolation from the host page
        const shadow = host.attachShadow({ mode: "open" });

        // Styles injected into shadow root (never into document.head)
        const styleEl = document.createElement("style");
        styleEl.textContent = STYLES;
        shadow.appendChild(styleEl);

        // Container with correct color tokens set BEFORE first render — no flash
        const container = document.createElement("div");
        container.style.cssText = "pointer-events:auto";
        container.style.setProperty("--cw-primary",   config.primaryColor);
        container.style.setProperty("--cw-secondary",  config.secondaryColor ?? darken(config.primaryColor, 0.4));
        shadow.appendChild(container);

        // Mount Preact with pre-loaded config — no loading state needed
        render(h(App, { orgId, apiBase, initialConfig: config }), container);
      })
      .catch(() => {
        // Config failed (bad org id, org disabled, webchat not enabled) — widget stays hidden entirely
      });
  }
}

function darken(hex: string, amount: number): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const num = parseInt(full, 16);
  const r = Math.max(0, ((num >> 16) & 0xff) * (1 - amount));
  const g = Math.max(0, ((num >> 8)  & 0xff) * (1 - amount));
  const b = Math.max(0, ((num)       & 0xff) * (1 - amount));
  return `#${[r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}
