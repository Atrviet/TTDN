/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172554",
        ocean: "#2563eb",
        mint: "#14b8a6",
        cloud: "#f5f7fb",
      },
      boxShadow: { card: "0 18px 45px -24px rgba(15, 23, 42, .28)" },
    },
  },
  plugins: [],
};
