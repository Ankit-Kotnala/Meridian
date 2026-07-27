import type {
  Resume,
  ResumeLayout,
  ResumeUpdateInput,
  ResumeVersion,
} from "../api/types";

export interface DraftBullet {
  entityId?: string | null;
  evidenceIds: string[];
  id: string;
  source: string;
  text: string;
}

export interface DraftSection {
  id: string;
  items: DraftBullet[];
  kind: string;
  title: string;
}

export interface ResumeDraft {
  title: string;
  targetRole: string;
  template: Resume["template"];
  layout: ResumeLayout;
  personalFactIds: string[];
  sections: DraftSection[];
}

export function draftFromResume(resume: Resume): ResumeDraft {
  return {
    layout: { ...resume.layout },
    personalFactIds: resume.currentVersion.personalFacts.map((fact) => fact.id),
    sections: resume.currentVersion.sections.map((section) => ({
      id: section.id,
      items: section.items.map((item) => ({
        entityId: item.entityId,
        evidenceIds: [...item.evidenceIds],
        id: item.id,
        source: item.source,
        text: item.text,
      })),
      kind: section.kind,
      title: section.title,
    })),
    targetRole: resume.targetRole ?? "",
    template: resume.template,
    title: resume.title,
  };
}

export function draftFromVersion(version: ResumeVersion): ResumeDraft {
  return {
    layout: { ...version.layout },
    personalFactIds: version.personalFacts.map((fact) => fact.id),
    sections: version.sections.map((section) => ({
      id: section.id,
      items: section.items.map((item) => ({
        entityId: item.entityId,
        evidenceIds: [...item.evidenceIds],
        id: item.id,
        source: item.source,
        text: item.text,
      })),
      kind: section.kind,
      title: section.title,
    })),
    targetRole: version.targetRole ?? "",
    template: version.template,
    title: version.title,
  };
}

export function draftUpdateInput(draft: ResumeDraft): ResumeUpdateInput {
  return {
    layout: draft.layout,
    personalFactIds: draft.personalFactIds,
    sections: draft.sections,
    targetRole: draft.targetRole.trim() || null,
    template: draft.template,
    title: draft.title.trim(),
  };
}

export function cloneDraft(draft: ResumeDraft): ResumeDraft {
  return {
    ...draft,
    layout: { ...draft.layout },
    personalFactIds: [...draft.personalFactIds],
    sections: draft.sections.map((section) => ({
      ...section,
      items: section.items.map((item) => ({
        ...item,
        evidenceIds: [...item.evidenceIds],
      })),
    })),
  };
}

export function sameDraft(left: ResumeDraft, right: ResumeDraft): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function draftPlainText(
  draft: ResumeDraft,
  personalFacts: ReadonlyArray<{ id: string; value: string }>,
): string {
  const selectedFacts = personalFacts
    .filter((fact) => draft.personalFactIds.includes(fact.id))
    .map((fact) => fact.value);
  return [
    ...selectedFacts,
    ...(draft.targetRole.trim() ? [draft.targetRole.trim()] : []),
    ...draft.sections.flatMap((section) => [
      section.title,
      ...section.items.map((item) => item.text),
    ]),
  ]
    .filter(Boolean)
    .join("\n");
}

export function changedLines(
  current: string,
  comparison: string,
): { currentOnly: string[]; comparisonOnly: string[] } {
  const currentLines = current.split("\n").filter(Boolean);
  const comparisonLines = comparison.split("\n").filter(Boolean);
  const currentSet = new Set(currentLines);
  const comparisonSet = new Set(comparisonLines);
  return {
    comparisonOnly: comparisonLines.filter((line) => !currentSet.has(line)),
    currentOnly: currentLines.filter((line) => !comparisonSet.has(line)),
  };
}
