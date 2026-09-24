/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        carbon: {
          950: "#050505",
          900: "#0a0a09",
          800: "#11110f",
          700: "#1d1d19",
          600: "#2b2b24",
        },
        holo: {
          DEFAULT: "#facc15",
          dark: "#a16207",
          soft: "#fef08a",
        },
        cat: "#facc15",
        danger: "#ef4444",
        warn: "#f59e0b",
        good: "#22c55e",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 22px -6px rgba(250,204,21,0.58)",
        "glow-amber": "0 0 22px -6px rgba(250,204,21,0.58)",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        pulseRing: {
          "0%": { transform: "scale(0.6)", opacity: "0.9" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        breathe: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        sweep: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        scan: "scan 9s linear infinite",
        pulseRing: "pulseRing 1.8s cubic-bezier(0.2,0.6,0.4,1) infinite",
        breathe: "breathe 2.2s ease-in-out infinite",
        sweep: "sweep 3.5s linear infinite",
      },
    },
  },
  plugins: [],
};
