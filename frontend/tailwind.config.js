/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(196,165,116,0.28)", opacity: "1" },
          "50%": { boxShadow: "0 0 36px 6px rgba(196,165,116,0.16)", opacity: "0.92" },
        },
        orbit: {
          to: { transform: "rotate(360deg)" },
        },
        scan: {
          "0%": { transform: "translateY(-20%)", opacity: "0" },
          "18%": { opacity: "0.7" },
          "100%": { transform: "translateY(320%)", opacity: "0" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-glow": "pulseGlow 2.2s ease-in-out infinite",
        orbit: "orbit 10s linear infinite",
        scan: "scan 2.8s ease-in-out infinite",
        rise: "rise 0.35s ease-out both",
      },
      colors: {
        ink: {
          950: "#0c0e12",
          900: "#12151b",
          800: "#181c24",
          700: "#1f2430",
          600: "#2a3140",
        },
        mist: {
          100: "#f4f1ea",
          300: "#c9c4b8",
          500: "#8b929e",
        },
        brass: {
          400: "#c4a574",
          500: "#b08d58",
        },
        pass: "#3d8b6e",
        warn: "#c4923a",
        fail: "#c45c5c",
        info: "#5b7c99",
      },
    },
  },
  plugins: [],
};
