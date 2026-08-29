export const fictionalDemoCareer = {
  fixture: true,
  fictional: true,
  profile: {
    displayName: "Alex Morgan",
    headline: "Senior Product Manager",
    location: "Bengaluru, India",
  },
  evidence: [
    {
      id: "demo-evidence-product-discovery",
      title: "Product discovery program",
      state: "confirmed",
      note: "Synthetic test data; not a claim about a real person.",
    },
  ],
} as const;
