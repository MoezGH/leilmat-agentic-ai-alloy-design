import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Vitest does not read tsconfig `paths`, so without this the `@/…` alias the
// rest of the app uses resolves to nothing under test — which is how
// lib/billing/client.ts came to import "../features" while its sibling
// lib/hooks/useCredits.ts imports "@/lib/features". One idiom, declared once.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
});
