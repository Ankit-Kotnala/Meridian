export const careerOsTheme = {
  color: {
    canvas: "#f5f7fb",
    surface: "#ffffff",
    sidebar: "#0b1739",
    primary: "#5b4ff7",
    verified: "#16865a",
    warning: "#b35f05",
    critical: "#c33d4a",
    text: "#101a3c",
    muted: "#5d6885",
    border: "#dde3ef",
  },
  radius: {
    card: "1rem",
    control: "0.75rem",
  },
  shadow: {
    card: "0 12px 30px rgba(11, 23, 57, 0.07)",
  },
} as const;

export type CareerOsTheme = typeof careerOsTheme;
