"use client";

import {
  ChevronRight,
  Download,
  ExternalLink,
  Library,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Tabs,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";
import { useInterviewPrepWorkspaceMetrics } from "@/shared/workspace/interview-prep-workspace-metrics";

import { getRoleRoadmap, getSkillLibrary } from "../api/career-growth-api";
import type {
  RoleRoadmap,
  RoadmapStage,
  SkillLibrary,
  SkillLibraryNote,
  SkillLibraryResource,
} from "../api/types";

function resourceCount(library: SkillLibrary["library"]): number {
  return (
    library.freeCourses.length +
    library.paidCourses.length +
    library.notes.length
  );
}

function downloadNotePdf(note: SkillLibraryNote) {
  const fileName = note.fileName.endsWith(".pdf")
    ? note.fileName
    : `${note.fileName.replace(/\.md$/i, "")}.pdf`;
  const bytes = buildSimplePdf(note.title, note.content);
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  const blob = new Blob([copy], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function buildSimplePdf(title: string, body: string): Uint8Array {
  const lines = wrapPdfLines(`${title}\n\n${body}`, 90);
  const pages: string[][] = [];
  const perPage = 54;
  for (let index = 0; index < lines.length; index += perPage) {
    pages.push(lines.slice(index, index + perPage));
  }
  if (pages.length === 0) pages.push([title]);

  const objects: string[] = ["<< /Type /Catalog /Pages 2 0 R >>"];
  const kids = pages.map((_, index) => `${3 + index * 2} 0 R`).join(" ");
  objects.push(`<< /Type /Pages /Kids [${kids}] /Count ${pages.length} >>`);
  pages.forEach((pageLines, index) => {
    const pageObjectNumber = 3 + index * 2;
    const contentObjectNumber = pageObjectNumber + 1;
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents ${contentObjectNumber} 0 R /Resources << /Font << /F1 ${3 + pages.length * 2} 0 R >> >> >>`,
    );
    const stream = pageLines
      .map((line, lineIndex) => {
        const y = 760 - lineIndex * 13;
        return `BT /F1 11 Tf 48 ${y} Td (${escapePdf(line)}) Tj ET`;
      })
      .join("\n");
    objects.push(
      `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    );
  });
  objects.push("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");

  let output = "%PDF-1.4\n";
  const offsets = [0];
  for (const [index, object] of objects.entries()) {
    offsets.push(output.length);
    output += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xref = output.length;
  output += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) {
    output += `${offset.toString().padStart(10, "0")} 00000 n \n`;
  }
  output += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new TextEncoder().encode(output);
}

function wrapPdfLines(text: string, width: number): string[] {
  const wrapped: string[] = [];
  for (const paragraph of text.replaceAll("\r\n", "\n").split("\n")) {
    if (!paragraph) {
      wrapped.push("");
      continue;
    }
    const words = paragraph.split(/\s+/);
    let current = "";
    for (const word of words) {
      const next = current ? `${current} ${word}` : word;
      if (next.length > width) {
        if (current) wrapped.push(current);
        current = word.length > width ? word.slice(0, width) : word;
      } else {
        current = next;
      }
    }
    if (current) wrapped.push(current);
  }
  return wrapped;
}

function escapePdf(value: string): string {
  return value
    .replaceAll("\\", "\\\\")
    .replaceAll("(", "\\(")
    .replaceAll(")", "\\)")
    .replaceAll(/[^\x20-\x7E]/g, " ");
}

function isCatalogSearch(url: string): boolean {
  return (
    url.includes("/search") ||
    url.includes("results?search") ||
    url.includes("page_search_query") ||
    /[?&](q|query|search|search_query|terms|keywords)=/.test(url)
  );
}

const FREE_GROUPS = [
  "Courses and videos",
  "Docs and lecture notes",
  "Browse catalogs",
] as const;

const PAID_GROUPS = [
  "Coursera",
  "Udemy",
  "edX and other courses",
  "Browse catalogs",
] as const;

function freeGroup(
  resource: SkillLibraryResource,
): (typeof FREE_GROUPS)[number] {
  if (isCatalogSearch(resource.url)) return "Browse catalogs";
  if (
    resource.kind === "docs" ||
    resource.kind === "lecture_notes" ||
    resource.kind === "khan_academy"
  ) {
    return "Docs and lecture notes";
  }
  return "Courses and videos";
}

function paidGroup(
  resource: SkillLibraryResource,
): (typeof PAID_GROUPS)[number] {
  if (isCatalogSearch(resource.url)) return "Browse catalogs";
  if (resource.kind === "coursera" || /coursera/i.test(resource.provider)) {
    return "Coursera";
  }
  if (resource.kind === "udemy" || /udemy/i.test(resource.provider)) {
    return "Udemy";
  }
  return "edX and other courses";
}

function groupedResources<T extends string>(
  resources: SkillLibraryResource[],
  groupOf: (resource: SkillLibraryResource) => T,
  order: readonly T[],
): { group: T; resources: SkillLibraryResource[] }[] {
  const buckets = new Map<T, SkillLibraryResource[]>();
  for (const label of order) buckets.set(label, []);
  for (const resource of resources) {
    const label = groupOf(resource);
    const bucket = buckets.get(label) ?? [];
    bucket.push(resource);
    buckets.set(label, bucket);
  }
  return order
    .map((group) => ({ group, resources: buckets.get(group) ?? [] }))
    .filter((entry) => entry.resources.length > 0);
}

function matchesQuery(resource: SkillLibraryResource, query: string): boolean {
  if (!query) return true;
  const haystack = `${resource.title} ${resource.provider}`.toLowerCase();
  return haystack.includes(query);
}

export function SkillLibraryPanel() {
  const searchParams = useSearchParams();
  const skillName = (searchParams.get("skill") ?? "").trim();
  const metrics = useInterviewPrepWorkspaceMetrics();
  const [roadmap, setRoadmap] = useState<RoleRoadmap | null>();
  const [library, setLibrary] = useState<SkillLibrary>();
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string>();
  const loadEpoch = useRef(0);

  const load = useCallback(async () => {
    const epoch = ++loadEpoch.current;
    setLoading(true);
    setFailure(undefined);
    try {
      const [roadmapValue, libraryValue] = await Promise.all([
        getRoleRoadmap(),
        skillName ? getSkillLibrary(skillName) : Promise.resolve(undefined),
      ]);
      if (epoch !== loadEpoch.current) return;
      setRoadmap(roadmapValue);
      setLibrary(libraryValue);
    } catch (error) {
      if (epoch !== loadEpoch.current) return;
      setFailure(
        requestErrorMessage(error, "The skill library could not be loaded."),
      );
    } finally {
      if (epoch === loadEpoch.current) setLoading(false);
    }
  }, [skillName]);

  useEffect(() => {
    void load();
    return () => {
      loadEpoch.current += 1;
    };
  }, [load]);

  const setLibraryResourceCount = metrics?.setLibraryResourceCount;
  const stages = roadmap?.stages ?? [];
  const skills = useMemo(
    () => stages.flatMap((stage) => stage.skills),
    [stages],
  );

  useEffect(() => {
    setLibraryResourceCount?.(skills.length);
  }, [setLibraryResourceCount, skills.length]);

  if (failure) {
    return (
      <main className="workspace-page" id="main-content">
        <ErrorState
          description={failure}
          onRetry={() => void load()}
          title="Skill library unavailable"
        />
      </main>
    );
  }

  if (loading) {
    return (
      <main className="workspace-page" id="main-content">
        <LoadingSkeleton variant="page" />
      </main>
    );
  }

  return (
    <main className="workspace-page space-y-6" id="main-content">
      <PageHeader
        description="Pick a skill from your path, then read the notes or open a course. Completion is not Career Record evidence."
        eyebrow="Interview Prep"
        title="Skill library"
      />

      <div className="grid gap-6 lg:grid-cols-[16.5rem_minmax(0,1fr)] lg:items-start">
        {stages.length > 0 ? (
          <SkillIndex
            activeName={library?.skillName ?? skillName}
            stages={stages}
          />
        ) : null}

        <div className="min-w-0">
          {!skillName ? (
            <EmptyState
              description="Choose a skill from the list to see study notes, free courses, and paid listings."
              title="Choose a skill"
            />
          ) : library ? (
            <LibraryCollections library={library} />
          ) : (
            <EmptyState
              description="This skill is not in the stored roadmap library yet."
              title="No library mapped"
            />
          )}
        </div>
      </div>
    </main>
  );
}

function SkillIndex({
  activeName,
  stages,
}: {
  activeName: string;
  stages: RoadmapStage[];
}) {
  return (
    <nav
      aria-label="Roadmap skills"
      className="workspace-panel max-h-56 overflow-y-auto p-3 lg:sticky lg:top-[8.5rem] lg:max-h-[calc(100vh-10rem)]"
    >
      <p className="px-2 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-muted">
        Your path
      </p>
      {stages.map((stage) => (
        <div className="mt-3" key={stage.stage}>
          <p className="px-2 text-[0.6875rem] font-semibold uppercase tracking-[0.06em] text-muted">
            {stage.stage}
          </p>
          <ul className="mt-1">
            {stage.skills.map((skill) => {
              const active = skill.name === activeName;
              return (
                <li key={skill.name}>
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-9 items-center rounded-[var(--radius-control)] px-2 text-[0.8125rem] leading-5 transition-colors",
                      active
                        ? "bg-info-soft font-semibold text-info"
                        : "font-medium text-foreground hover:bg-surface-subtle",
                    )}
                    href={`/interview-prep/library?skill=${encodeURIComponent(skill.name)}`}
                  >
                    {skill.name}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function LibraryCollections({ library }: { library: SkillLibrary }) {
  const contents = library.library;
  const total = resourceCount(contents);

  return (
    <div className="space-y-4">
      <section className="workspace-panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-muted">Mapped skill</p>
            <h2 className="mt-1 font-display text-xl font-semibold tracking-[-0.02em] text-foreground">
              {library.skillName}
            </h2>
          </div>
          <Badge tone="primary">
            <Library aria-hidden="true" className="size-3.5" />
            {total} resources
          </Badge>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          {library.why}
        </p>
        {library.howToStart ? (
          <p className="mt-4 rounded-[var(--radius-control)] border border-line bg-surface-subtle px-4 py-3 text-sm leading-6 text-muted-strong">
            <strong className="font-semibold text-foreground">
              Start here:
            </strong>{" "}
            {library.howToStart}
          </p>
        ) : null}
      </section>

      <Tabs
        defaultValue="notes"
        label="Library collections"
        tabs={[
          {
            id: "notes",
            label: `Study notes (${contents.notes.length})`,
            panel: (
              <div className="pt-4">
                <NotesGroup notes={contents.notes} />
              </div>
            ),
          },
          {
            id: "free",
            label: `Free courses (${contents.freeCourses.length})`,
            panel: (
              <div className="pt-4">
                <ResourceGroup
                  empty="No free courses are mapped for this skill yet."
                  filterLabel="Filter free courses"
                  groupOf={freeGroup}
                  order={FREE_GROUPS}
                  resources={contents.freeCourses}
                />
              </div>
            ),
          },
          {
            id: "paid",
            label: `Paid courses (${contents.paidCourses.length})`,
            panel: (
              <div className="pt-4">
                <ResourceGroup
                  empty="No paid courses are mapped for this skill yet."
                  filterLabel="Filter paid courses"
                  groupOf={paidGroup}
                  order={PAID_GROUPS}
                  resources={contents.paidCourses}
                />
              </div>
            ),
          },
        ]}
      />

      <Alert title="Third-party resources" tone="info">
        {library.disclaimer}
      </Alert>
    </div>
  );
}

function ResourceGroup<T extends string>({
  empty,
  filterLabel,
  groupOf,
  order,
  resources,
}: {
  empty: string;
  filterLabel: string;
  groupOf: (resource: SkillLibraryResource) => T;
  order: readonly T[];
  resources: SkillLibraryResource[];
}) {
  const filterId = useId();
  const [query, setQuery] = useState("");
  const normalized = query.trim().toLowerCase();
  const visible = resources.filter((resource) =>
    matchesQuery(resource, normalized),
  );
  const groups = groupedResources(visible, groupOf, order);

  if (resources.length === 0) {
    return <p className="text-sm text-muted">{empty}</p>;
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
        />
        <Input
          aria-label={filterLabel}
          className="pl-9"
          id={filterId}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter by title or provider"
          type="search"
          value={query}
        />
      </div>
      {groups.length === 0 ? (
        <p className="text-sm text-muted">
          No resources match “{query.trim()}”.
        </p>
      ) : (
        groups.map((entry) => (
          <section key={entry.group}>
            <h3 className="text-sm font-semibold tracking-[-0.01em] text-foreground">
              {entry.group}
              <span className="ml-2 font-medium text-muted">
                {entry.resources.length}
              </span>
            </h3>
            <ul className="mt-2 divide-y divide-line overflow-hidden rounded-[var(--radius-control)] border border-line bg-surface">
              {entry.resources.map((resource) => (
                <li key={resource.url}>
                  <a
                    className="flex items-start justify-between gap-3 px-3 py-3 text-left transition-colors hover:bg-surface-subtle focus-visible:bg-surface-subtle"
                    href={resource.url}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    <span className="min-w-0">
                      <span className="block font-semibold text-foreground">
                        {resource.title}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {resource.provider}
                      </span>
                    </span>
                    <span className="inline-flex shrink-0 items-center gap-1 pt-0.5 text-xs font-semibold text-info">
                      Open
                      <ExternalLink aria-hidden="true" className="size-3.5" />
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}

function NotesGroup({ notes }: { notes: SkillLibraryNote[] }) {
  if (notes.length === 0) {
    return (
      <p className="text-sm text-muted">
        No readable notes are mapped for this skill yet.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {notes.map((note, index) => (
        <li key={note.fileName}>
          <details className="group workspace-panel" open={index === 0}>
            <summary className="flex cursor-pointer list-none items-start gap-2 px-4 py-3 sm:px-5 [&::-webkit-details-marker]:hidden">
              <ChevronRight
                aria-hidden="true"
                className="mt-1 size-4 shrink-0 text-muted transition-transform group-open:rotate-90 motion-reduce:transition-none"
              />
              <span>
                <span className="block font-semibold text-foreground">
                  {note.title}
                </span>
                <span className="mt-1 block text-sm text-muted">
                  Readable study article. Expand to read, or download a PDF.
                </span>
              </span>
            </summary>
            <div className="border-t border-line px-4 py-4 sm:px-5">
              <div className="mb-4 flex justify-end">
                <Button
                  onClick={() => downloadNotePdf(note)}
                  variant="secondary"
                >
                  <Download aria-hidden="true" className="size-4" />
                  Download PDF
                </Button>
              </div>
              <NoteArticle content={note.content} />
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}

function NoteArticle({ content }: { content: string }) {
  const blocks = content.split(/\n\n+/);
  return (
    <div className="max-w-3xl space-y-4 text-sm leading-7 text-muted-strong">
      {blocks.map((block, index) => {
        const lines = block.split("\n");
        const heading = lines[0] ?? "";
        const rest = lines.slice(1);
        const isList =
          rest.length > 0 && rest.every((line) => /^-\s/.test(line));
        const isHeading =
          rest.length > 0 && heading.length < 80 && !heading.endsWith(".");
        if (isHeading && isList) {
          return (
            <div key={`${heading}-${index}`}>
              <h4 className="font-semibold text-foreground">{heading}</h4>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {rest.map((line) => (
                  <li key={line}>{line.replace(/^-\s+/, "")}</li>
                ))}
              </ul>
            </div>
          );
        }
        if (isHeading) {
          return (
            <div key={`${heading}-${index}`}>
              <h4 className="font-semibold text-foreground">{heading}</h4>
              <p className="mt-2 whitespace-pre-wrap">{rest.join("\n")}</p>
            </div>
          );
        }
        if (lines.every((line) => /^-\s/.test(line))) {
          return (
            <ul className="list-disc space-y-1 pl-5" key={index}>
              {lines.map((line) => (
                <li key={line}>{line.replace(/^-\s+/, "")}</li>
              ))}
            </ul>
          );
        }
        return (
          <p className="whitespace-pre-wrap" key={index}>
            {block}
          </p>
        );
      })}
    </div>
  );
}
