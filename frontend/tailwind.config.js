/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Space Grotesk", "Segoe UI", "sans-serif"],
        body: ["IBM Plex Sans", "Segoe UI", "sans-serif"]
      },
      boxShadow: {
        glow: "0 0 28px rgba(56, 189, 248, 0.35)"
      }
    }
  },
  plugins: []
};
