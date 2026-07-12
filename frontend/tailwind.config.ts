import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary dark background system
        surface: {
          900: "#080C12",
          800: "#0D1117",
          700: "#111820",
          600: "#161E28",
          500: "#1C2733",
          400: "#243040",
        },
        // Accent — electric teal / cyan
        accent: {
          DEFAULT: "#00D4FF",
          dim: "#0099BB",
          glow: "#00D4FF33",
        },
        // Alert severity colors
        severity: {
          high: "#FF3B3B",
          "high-dim": "#FF3B3B22",
          medium: "#FF9F0A",
          "medium-dim": "#FF9F0A22",
          low: "#34C759",
          "low-dim": "#34C75922",
          info: "#5E5CE6",
          "info-dim": "#5E5CE622",
        },
        // Text hierarchy
        ink: {
          primary: "#E8EDF3",
          secondary: "#8B95A3",
          muted: "#4A5568",
          accent: "#00D4FF",
        },
        // Border
        border: {
          DEFAULT: "#1C2733",
          bright: "#243040",
          accent: "#00D4FF44",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        display: ["'Space Mono'", "monospace"],
      },
      animation: {
        "pulse-dot": "pulse-dot 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "scan-line": "scan-line 3s linear infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in": "slide-in 0.3s ease-out",
        blink: "blink 1s step-end infinite",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
        "scan-line": {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-in": {
          "0%": { transform: "translateX(-8px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
      boxShadow: {
        accent: "0 0 20px #00D4FF22",
        "accent-strong": "0 0 40px #00D4FF44",
        "severity-high": "0 0 20px #FF3B3B33",
        "severity-medium": "0 0 20px #FF9F0A33",
        panel: "0 4px 24px rgba(0,0,0,0.4)",
      },
    },
  },
  plugins: [],
};
export default config;
