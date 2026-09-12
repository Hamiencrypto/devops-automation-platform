import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // True neutral (no blue cast) — the near-monochrome base. Tailwind's
        // `slate` leans blue, which fights with blue being reserved below
        // for exactly one meaning: a call denied by policy.
        canvas: {
          DEFAULT: "#ffffff",
          sunken: "#fafafa",
          dark: "#0a0a0a",
          "dark-sunken": "#111113",
          "dark-raised": "#18181b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
