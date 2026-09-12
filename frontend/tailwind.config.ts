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
        canvas: {
          DEFAULT: "#ffffff",
          sunken: "#f7f7fb",
          dark: "#0a0a12",
          "dark-sunken": "#0d0d16",
          "dark-raised": "#15151f",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "gradient-brand": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%)",
        "gradient-brand-soft":
          "linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.15) 50%, rgba(6,182,212,0.15) 100%)",
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(31, 38, 135, 0.10)",
        "glass-dark": "0 8px 32px 0 rgba(0, 0, 0, 0.35)",
        glow: "0 0 24px -4px rgba(99, 102, 241, 0.5)",
        "glow-lg": "0 0 40px -6px rgba(99, 102, 241, 0.55)",
      },
      keyframes: {
        blob: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)" },
          "33%": { transform: "translate(4%, -6%) scale(1.08)" },
          "66%": { transform: "translate(-3%, 4%) scale(0.95)" },
        },
      },
      animation: {
        blob: "blob 22s ease-in-out infinite",
        "blob-slow": "blob 30s ease-in-out infinite reverse",
      },
    },
  },
  plugins: [],
};

export default config;
