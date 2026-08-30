import type { Skill } from "../api/types";

export type SkillDomainTone =
  "ai" | "cloud" | "data" | "language" | "other" | "practice" | "web";

export type SkillDomain = {
  id: string;
  label: string;
  skills: Skill[];
  tone: SkillDomainTone;
};

/**
 * Grouping is presentation, not a new claim.
 *
 * Every skill shown in a domain is one the owner actually recorded; the domain
 * only decides which cluster it is drawn in. Rules match the recorded name and
 * the owner's own category together, so an explicit category like "AI / LLM"
 * lands in the same cluster as a bare "LangGraph". Order matters — the first
 * matching rule wins.
 */
const domainRules: readonly {
  id: string;
  label: string;
  pattern: RegExp;
  tone: SkillDomainTone;
}[] = [
  {
    id: "artificial-intelligence",
    label: "Artificial Intelligence",
    pattern:
      /\b(ai|genai|generative|llm|llms|gpt|claude|openai|anthropic|gemini|langchain|langgraph|llamaindex|rag|prompt|prompting|embedding|embeddings|transformer|transformers|hugging ?face|nlp|nl-to-sql|text-to-sql|vector|pytorch|tensorflow|keras|scikit-?learn|sklearn|machine learning|deep learning|ml|mlops|computer vision|agent|agents|agentic|fine-?tun\w*)\b/,
    tone: "ai",
  },
  {
    id: "cloud-and-infrastructure",
    label: "Cloud & Infrastructure",
    pattern:
      /\b(aws|amazon web services|azure|gcp|google cloud|cloud|docker|kubernetes|k8s|terraform|pulumi|ansible|ci\/cd|github actions|gitlab ci|jenkins|serverless|lambda|ec2|s3|minio|celery|redis|rabbitmq|kafka|nginx|linux|devops|sre|observability|grafana|prometheus)\b/,
    tone: "cloud",
  },
  {
    id: "data-and-analytics",
    label: "Data & Analytics",
    pattern:
      /\b(sql|postgres|postgresql|mysql|sqlite|mongodb|mongo|qdrant|pinecone|weaviate|elasticsearch|opensearch|database|databases|etl|elt|data engineering|analytics|pandas|numpy|spark|airflow|dbt|warehouse|bigquery|snowflake|redshift|tableau|power ?bi)\b/,
    tone: "data",
  },
  {
    id: "web-development",
    label: "Web Development",
    pattern:
      /\b(react|next\.?js|node|node\.?js|deno|typescript|javascript|html|css|tailwind|sass|frontend|front-?end|backend|back-?end|full-?stack|api|apis|rest|graphql|grpc|fastapi|django|flask|express|nest\.?js|spring|vue|angular|svelte|accessibility|wcag)\b/,
    tone: "web",
  },
  {
    id: "programming-languages",
    label: "Programming Languages",
    pattern:
      /\b(python|java|c\+\+|c#|\.net|golang|go|rust|ruby|php|kotlin|swift|scala|r|matlab|bash|shell)\b/,
    tone: "language",
  },
  {
    id: "ways-of-working",
    label: "Ways of Working",
    pattern:
      /\b(agile|scrum|kanban|product|roadmap|stakeholder|leadership|mentoring|mentorship|communication|facilitation|discovery|user research|ux|ui|figma|design|writing|documentation|testing|qa|security|compliance)\b/,
    tone: "practice",
  },
];

function haystack(skill: Skill): string {
  return `${skill.name} ${skill.category ?? ""}`.toLowerCase();
}

function categoryId(category: string): string {
  return `category-${category
    .trim()
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, "-")}`;
}

export function groupSkillsByDomain(skills: readonly Skill[]): SkillDomain[] {
  const groups = new Map<string, SkillDomain>();
  for (const skill of skills) {
    const rule = domainRules.find((candidate) =>
      candidate.pattern.test(haystack(skill)),
    );
    const category = skill.category?.trim();
    const id = rule?.id ?? (category ? categoryId(category) : "other-skills");
    const existing = groups.get(id);
    if (existing) {
      existing.skills.push(skill);
      continue;
    }
    groups.set(id, {
      id,
      label: rule?.label ?? category ?? "Other skills",
      skills: [skill],
      tone: rule?.tone ?? "other",
    });
  }
  return [...groups.values()]
    .map((domain) => ({
      ...domain,
      skills: [...domain.skills].sort((left, right) =>
        left.name.localeCompare(right.name),
      ),
    }))
    .sort(
      (left, right) =>
        right.skills.length - left.skills.length ||
        left.label.localeCompare(right.label),
    );
}

/**
 * Circle area tracks how many skills a domain holds, so the largest cluster
 * reads as the largest bubble without any single skill being over-weighted.
 */
export function domainCircleSize(count: number): string {
  if (count >= 10) return "9rem";
  if (count >= 7) return "8.25rem";
  if (count >= 4) return "7.5rem";
  if (count >= 2) return "6.75rem";
  return "6rem";
}
