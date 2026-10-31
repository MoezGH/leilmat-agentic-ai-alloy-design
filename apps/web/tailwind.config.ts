import type { Config } from "tailwindcss";

/** A colour from a CSS variable of RGB channels (app/globals.css), so Tailwind's opacity modifiers work: bg-surface/80. */
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // The INFINITE palette itself (brand guidelines, section 09): red is the accent, one strong element per view.
        infinite: { red: "#E30613", ink: "#141414", paper: "#F4F1EA", grey: "#6F6D67", rule: "#CFCBC2" },

        // Roles, set per theme in globals.css. Components use these, never a raw palette colour.
        bg: v("bg"),              // the page
        surface: v("surface"),    // panels, header, footer
        raised: v("raised"),      // inputs, tiles, menus on a panel
        line: v("line"),          // hairlines and borders
        fg: v("fg"),              // text; also selection, links and filled buttons (Paper on Ink, Ink on Paper)
        muted: v("muted"),        // secondary text, labels
        subtle: v("subtle"),      // hints, disabled
        brand: v("brand"),        // Infinite Red: the ONE primary action of a view — never selection or links
        ok: v("ok"),              // status: converged, balanced, check passed
        warn: v("warn"),          // status: check this
        bad: v("danger"),         // status: failed — deliberately not the brand red
        viewport: v("viewport"),  // behind charts and canvases
      },
      fontFamily: {
        sans: ["Barlow", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ['"Barlow Condensed"', '"Arial Narrow"', "sans-serif"],   // 900, uppercase
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      letterSpacing: {
        label: "0.16em",          // mono labels (brand: tracking +16 %)
        display: "-0.02em",       // condensed headlines (brand: −2 %)
      },
    },
  },
  plugins: [],
};

export default config;
