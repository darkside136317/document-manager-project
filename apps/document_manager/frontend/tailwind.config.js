/** Colours come from the shared brand tokens (public/css/theme-tokens.css), so a re-brand is one file. */
const token = (name) => `var(--dm-${name})`;

export default {
  content: ["./src/**/*.{vue,js}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: token("primary"), hover: token("primary-hover"), soft: token("primary-soft") },
        accent: { DEFAULT: token("accent"), hover: token("accent-hover"), soft: token("accent-soft") },
        ink: { DEFAULT: token("ink"), soft: token("ink-soft"), muted: token("muted"), subtle: token("subtle") },
        line: { DEFAULT: token("border"), strong: token("border-strong") },
        surface: { DEFAULT: token("surface"), muted: token("surface-muted") },
        canvas: token("background"),
        success: { DEFAULT: token("success"), soft: token("success-soft") },
        warning: { DEFAULT: token("warning"), soft: token("warning-soft") },
        danger: { DEFAULT: token("danger"), soft: token("danger-soft") },
        info: { DEFAULT: token("info"), soft: token("info-soft") },
      },
      fontFamily: {
        sans: ['"Segoe UI"', "system-ui", "-apple-system", "Roboto", '"Helvetica Neue"', "Arial", "sans-serif"],
      },
      borderRadius: { md: token("radius-sm"), lg: token("radius-md"), xl: token("radius-lg") },
      boxShadow: { card: token("shadow-sm"), pop: token("shadow-lg") },
    },
  },
};
