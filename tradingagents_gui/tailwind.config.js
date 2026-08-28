/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#131722",
          secondary: "#1E222D",
          surface: "#2A2E39",
          hover: "#313642",
        },
        accent: {
          DEFAULT: "#2962FF",
          hover: "#1E53E5",
          dim: "#1E49BE",
        },
        up: "#089981",
        down: "#F23645",
        warn: "#D6A846",
        text: {
          primary: "#D1D4DC",
          secondary: "#787B86",
          muted: "#5A5D68",
        },
        line: "#363A45",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Microsoft YaHei",
          "PingFang SC",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "SFMono-Regular",
          "Consolas",
          "Liberation Mono",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.3)",
        "glow-accent": "0 0 20px rgba(41,98,255,0.35), 0 0 60px rgba(41,98,255,0.12)",
        "glow-accent-sm": "0 0 12px rgba(41,98,255,0.4)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(200%)" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.3s ease-out both",
        shimmer: "shimmer 2s linear infinite",
        "pulse-glow": "pulse-glow 2.5s ease-in-out infinite",
        "spin-slow": "spin-slow 8s linear infinite",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
