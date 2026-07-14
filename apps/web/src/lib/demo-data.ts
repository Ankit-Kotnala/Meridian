export const demoFixture = {
  fixtureNotice:
    "All names, organizations, roles, scores, dates, activities, and outcomes on this page are fictional demo data.",
  profile: {
    name: "Jordan Lee",
    initials: "JL",
    targetRole: "Senior Product Manager",
  },
  metrics: [
    {
      label: "Resume Health",
      value: "78",
      unit: "/100",
      note: "Strong baseline",
      tone: "success",
    },
    {
      label: "Role Readiness",
      value: "72",
      unit: "%",
      note: "Senior Product Manager",
      tone: "warning",
    },
    {
      label: "Applications",
      value: "24",
      unit: "",
      note: "Fictional active search",
      tone: "primary",
    },
    {
      label: "Interviews",
      value: "5",
      unit: "",
      note: "Across demo pipeline",
      tone: "primary",
    },
  ],
  resumeScores: [
    { label: "Machine Readability", score: 92, tone: "success" },
    { label: "Content Impact", score: 70, tone: "primary" },
    { label: "Recruiter Clarity", score: 75, tone: "primary" },
    { label: "Consistency", score: 80, tone: "success" },
    { label: "Achievement Strength", score: 65, tone: "warning" },
  ],
  readiness: [
    { label: "Product strategy", score: 88, state: "Demonstrated" },
    { label: "User research", score: 82, state: "Demonstrated" },
    { label: "Data analysis", score: 76, state: "Supported" },
    { label: "P&L ownership", score: 28, state: "Missing evidence" },
  ],
  activities: [
    {
      title: "Career profile reviewed",
      context: "8 fictional evidence links confirmed",
      time: "2 hours ago",
      tone: "success",
    },
    {
      title: "Application moved to interview",
      context: "Aurora Systems · Senior PM",
      time: "Yesterday",
      tone: "primary",
    },
    {
      title: "Evidence question created",
      context: "Clarify the measured launch outcome",
      time: "2 days ago",
      tone: "warning",
    },
    {
      title: "Resume version exported",
      context: "Round-trip verification passed",
      time: "4 days ago",
      tone: "success",
    },
  ],
  pipeline: [
    { label: "Saved", count: 12, color: "bg-slate-400" },
    { label: "Applied", count: 24, color: "bg-primary" },
    { label: "Interview", count: 5, color: "bg-[#2d8de0]" },
    { label: "Offer", count: 2, color: "bg-success" },
  ],
  evidence: {
    confirmed: 18,
    questions: 3,
    unsupported: 1,
  },
  applications: [
    {
      company: "Aurora Systems",
      role: "Senior Product Manager",
      stage: "Interview",
      date: "Round 2 · Fri",
      tone: "primary",
    },
    {
      company: "Northstar Labs",
      role: "Product Lead",
      stage: "Applied",
      date: "3 days ago",
      tone: "neutral",
    },
    {
      company: "Fieldwork Cloud",
      role: "Platform PM",
      stage: "Preparing",
      date: "Due Thursday",
      tone: "warning",
    },
  ],
} as const;

export type DemoMetricTone = (typeof demoFixture.metrics)[number]["tone"];
