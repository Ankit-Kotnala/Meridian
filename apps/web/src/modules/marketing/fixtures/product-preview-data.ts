export const productPreviewFixture = {
  profile: {
    firstName: "Jordan",
    initials: "JL",
  },
  resumeHealth: {
    score: 78,
    summary: "Strong foundation",
    focusedImprovements: 3,
  },
  readinessBreakdown: [
    { label: "Machine readability", score: 92, color: "bg-success" },
    { label: "Recruiter clarity", score: 76, color: "bg-primary" },
    { label: "Achievement strength", score: 68, color: "bg-[#e59a1f]" },
  ],
  nextSteps: ["Confirm one metric", "Add project evidence", "Review role gaps"],
} as const;
