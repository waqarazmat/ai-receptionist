import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { resolve } from "path";

export default defineConfig({
  plugins: [preact()],
  define: {
    // Baked-in API base — overridable at runtime via data-api-base attribute on the script tag.
    // Defaults to this backend's real dev port (see backend/CLAUDE.md); set
    // VITE_API_BASE to the production API origin for the genaitech.be build.
    __API_BASE__: JSON.stringify(process.env["VITE_API_BASE"] ?? "http://localhost:8000"),
  },
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      name: "PlatformWidget",
      formats: ["iife"],
      // Matches the intended hosted path https://genaitech.be/widget/cw.js
      fileName: () => "cw.js",
    },
    rollupOptions: {
      output: {
        // Everything in one file — no dynamic splits
        inlineDynamicImports: true,
      },
    },
    // CSS is authored as a TS string (styles.ts) and injected into shadow root —
    // no separate .css file is emitted.
    cssCodeSplit: false,
    minify: true,
    outDir: "dist",
  },
});
