import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f1f1f",
        line: "#e6e6e6",
        mist: "#f6f7f8",
        accent: "#1a73e8",
      },
    },
  },
  plugins: [],
};

export default config;
