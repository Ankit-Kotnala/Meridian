import { describe, expect, it } from "vitest";

import type { Skill } from "../api/types";
import {
  domainCircleSize,
  groupSkillsByDomain,
} from "../components/skill-domains";

function skill(name: string, category: string | null = null): Skill {
  return {
    category,
    createdAt: "2026-07-15T00:00:00Z",
    id: `id-${name}`,
    name,
    order: 0,
    proficiency: null,
    provenance: [],
    updatedAt: "2026-07-15T00:00:00Z",
    userConfirmed: false,
    version: 1,
  };
}

describe("skill domain grouping", () => {
  it("clusters recorded AI skills under one domain", () => {
    const domains = groupSkillsByDomain([
      skill("Generative AI"),
      skill("LangGraph"),
      skill("LangChain"),
      skill("RAG"),
      skill("Docker"),
    ]);

    const ai = domains.find(
      (domain) => domain.label === "Artificial Intelligence",
    );
    expect(ai?.skills.map((value) => value.name)).toEqual([
      "Generative AI",
      "LangChain",
      "LangGraph",
      "RAG",
    ]);
    expect(
      domains.find((domain) => domain.label === "Cloud & Infrastructure")
        ?.skills,
    ).toHaveLength(1);
  });

  it("matches the owner's own category text as well as the skill name", () => {
    const domains = groupSkillsByDomain([
      skill("Fictional model tool", "AI / LLM"),
    ]);

    expect(domains[0]?.label).toBe("Artificial Intelligence");
  });

  it("keeps an unmatched category as its own cluster rather than inventing one", () => {
    const domains = groupSkillsByDomain([
      skill("Fictional craft", "Studio craft"),
      skill("Another craft", "Studio craft"),
      skill("Uncategorised thing"),
    ]);

    expect(domains[0]).toMatchObject({ label: "Studio craft", tone: "other" });
    expect(domains[0]?.skills).toHaveLength(2);
    expect(domains[1]?.label).toBe("Other skills");
  });

  it("orders the largest cluster first and scales its circle", () => {
    const domains = groupSkillsByDomain([
      skill("Python"),
      skill("AWS"),
      skill("Docker"),
      skill("Kubernetes"),
    ]);

    expect(domains[0]?.label).toBe("Cloud & Infrastructure");
    expect(domains[0]?.skills).toHaveLength(3);
    expect(domainCircleSize(domains[0]?.skills.length ?? 0)).toBe("6.75rem");
    expect(domainCircleSize(1)).toBe("6rem");
    expect(domainCircleSize(12)).toBe("9rem");
  });

  it("never drops or duplicates a recorded skill", () => {
    const skills = [
      skill("Generative AI"),
      skill("React"),
      skill("PostgreSQL"),
      skill("User research"),
      skill("Something unmatched"),
    ];

    const grouped = groupSkillsByDomain(skills).flatMap(
      (domain) => domain.skills,
    );

    expect(grouped).toHaveLength(skills.length);
    expect(new Set(grouped.map((value) => value.id)).size).toBe(skills.length);
  });
});
