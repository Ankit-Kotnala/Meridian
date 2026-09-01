"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Button,
  Card,
  CheckboxField,
  FieldLabel,
  LoadingSkeleton,
  Select,
  TextField,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getApplicationProfile,
  upsertApplicationProfile,
} from "../api/applications-api";
import type { ApplicationProfile, ApplicationProfileLink } from "../api/types";
import {
  CATALOG_DISCLOSURE_KEYS,
  MAX_VOLUNTARY_DISCLOSURES,
  QUESTIONNAIRE_ACK_KEY,
  QUESTIONNAIRE_ACK_VALUE,
  QUESTIONNAIRE_SECTIONS,
  WORK_AUTHORIZATION_OPTIONS,
  asHttpUrl,
  withCurrentValue,
  type QuestionnaireField,
} from "./application-questionnaire";

type ExtraRow = { key: string; value: string };

function splitLocations(value: string): string[] {
  return value
    .split(",")
    .map((location) => location.trim())
    .filter(Boolean);
}

function numberField(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function splitDisclosures(disclosures: Record<string, string> | undefined): {
  acknowledged: boolean;
  answers: Record<string, string>;
  extra: ExtraRow[];
} {
  const answers: Record<string, string> = {};
  const extra: ExtraRow[] = [];
  let acknowledged = false;
  for (const [key, value] of Object.entries(disclosures ?? {})) {
    if (key === QUESTIONNAIRE_ACK_KEY) {
      acknowledged = value === QUESTIONNAIRE_ACK_VALUE;
      continue;
    }
    if (CATALOG_DISCLOSURE_KEYS.has(key)) {
      answers[key] = value;
    } else {
      extra.push({ key, value });
    }
  }
  return { acknowledged, answers, extra };
}

function disclosureValue(
  disclosures: Record<string, string>,
  key: string,
): string {
  return disclosures[key] ?? "";
}

function FieldControl({
  field,
  onChange,
  value,
}: {
  field: QuestionnaireField;
  onChange: (value: string) => void;
  value: string;
}) {
  if (field.kind === "select" && field.options) {
    const options = withCurrentValue(field.options, value);
    return (
      <div className="space-y-2">
        <FieldLabel htmlFor={field.key}>{field.label}</FieldLabel>
        <Select
          id={field.key}
          onChange={(event) => onChange(event.target.value)}
          value={value}
        >
          {options.map((option) => (
            <option key={`${field.key}:${option.value}`} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        {field.hint ? (
          <p className="text-xs leading-5 text-muted">{field.hint}</p>
        ) : null}
      </div>
    );
  }

  return (
    <TextField
      hint={field.hint}
      id={field.key}
      label={field.label}
      maxLength={field.maxLength ?? 500}
      onChange={(event) => onChange(event.target.value)}
      placeholder={field.placeholder}
      value={value}
    />
  );
}

/**
 * Owner-entered answers reused by the assisted-apply handoff pack.
 * Meridian never infers protected characteristics from a resume.
 */
export function ApplicationProfilePanel() {
  const [loaded, setLoaded] = useState(false);
  const [workAuthorization, setWorkAuthorization] = useState("");
  const [noticePeriodDays, setNoticePeriodDays] = useState("");
  const [compensationMin, setCompensationMin] = useState("");
  const [compensationMax, setCompensationMax] = useState("");
  const [compensationCurrency, setCompensationCurrency] = useState("USD");
  const [preferredLocations, setPreferredLocations] = useState("");
  const [profileLinks, setProfileLinks] = useState<ApplicationProfileLink[]>(
    [],
  );
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [extraRows, setExtraRows] = useState<ExtraRow[]>([]);
  const [acknowledged, setAcknowledged] = useState(false);
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [saving, setSaving] = useState(false);

  const applyProfile = useCallback((profile: ApplicationProfile) => {
    setWorkAuthorization(profile.workAuthorization ?? "");
    setNoticePeriodDays(numberField(profile.noticePeriodDays));
    setCompensationMin(numberField(profile.compensationMin));
    setCompensationMax(numberField(profile.compensationMax));
    setCompensationCurrency(profile.compensationCurrency || "USD");
    setPreferredLocations((profile.preferredLocations ?? []).join(", "));
    setProfileLinks(profile.profileLinks ?? []);
    const next = splitDisclosures(profile.voluntaryDisclosures);
    setAcknowledged(next.acknowledged);
    setAnswers(next.answers);
    setExtraRows(next.extra);
  }, []);

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const profile = await getApplicationProfile();
      if (!profile) {
        return;
      }
      applyProfile(profile);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "Your application answers could not be loaded.",
        ),
      );
    } finally {
      setLoaded(true);
    }
  }, [applyProfile]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  const catalogFieldCount = QUESTIONNAIRE_SECTIONS.reduce(
    (total, section) => total + section.fields.length,
    0,
  );
  const answeredCount = useMemo(() => {
    const firstClass = [
      workAuthorization,
      noticePeriodDays,
      compensationMin,
      compensationMax,
      preferredLocations,
    ].filter((value) => value.trim()).length;
    const catalog = Object.values(answers).filter((value) =>
      value.trim(),
    ).length;
    return firstClass + catalog;
  }, [
    answers,
    compensationMax,
    compensationMin,
    noticePeriodDays,
    preferredLocations,
    workAuthorization,
  ]);

  function setAnswer(key: string, value: string) {
    setAnswers((current) => ({ ...current, [key]: value }));
  }

  function addLink() {
    setProfileLinks((current) => [...current, { label: "", url: "" }]);
  }

  function updateLink(index: number, next: Partial<ApplicationProfileLink>) {
    setProfileLinks((current) =>
      current.map((link, itemIndex) =>
        itemIndex === index ? { ...link, ...next } : link,
      ),
    );
  }

  function removeLink(index: number) {
    setProfileLinks((current) => current.filter((_, i) => i !== index));
  }

  function addExtra() {
    setExtraRows((current) => [...current, { key: "", value: "" }]);
  }

  function updateExtra(index: number, next: Partial<ExtraRow>) {
    setExtraRows((current) =>
      current.map((row, itemIndex) =>
        itemIndex === index ? { ...row, ...next } : row,
      ),
    );
  }

  function removeExtra(index: number) {
    setExtraRows((current) => current.filter((_, i) => i !== index));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!acknowledged) {
      setFailure(
        "Confirm that these answers are yours and will be stored for Apply for me.",
      );
      return;
    }
    const currency = compensationCurrency.trim().toUpperCase() || "USD";
    if (!/^[A-Z]{3}$/.test(currency)) {
      setFailure("Compensation currency must be a 3-letter ISO code.");
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const voluntaryDisclosures: Record<string, string> = {
        [QUESTIONNAIRE_ACK_KEY]: QUESTIONNAIRE_ACK_VALUE,
      };
      for (const [key, value] of Object.entries(answers)) {
        const trimmed = value.trim();
        if (trimmed) voluntaryDisclosures[key] = trimmed;
      }
      for (const row of extraRows) {
        const key = row.key
          .trim()
          .toLowerCase()
          .replaceAll(/[^a-z0-9_]/g, "_");
        const value = row.value.trim();
        if (
          key.length >= 3 &&
          key !== QUESTIONNAIRE_ACK_KEY &&
          !CATALOG_DISCLOSURE_KEYS.has(key) &&
          value
        ) {
          voluntaryDisclosures[key] = value;
        }
      }
      if (
        Object.keys(voluntaryDisclosures).length > MAX_VOLUNTARY_DISCLOSURES
      ) {
        setFailure(
          "Too many custom answers. Remove extra rows or leave unused catalog questions blank.",
        );
        return;
      }
      const links = profileLinks
        .map((link) => ({
          label: link.label.trim(),
          url: asHttpUrl(link.url),
        }))
        .filter((link) => link.label && link.url);
      const saved = await upsertApplicationProfile({
        compensationCurrency: currency,
        compensationMax: compensationMax ? Number(compensationMax) : null,
        compensationMin: compensationMin ? Number(compensationMin) : null,
        noticePeriodDays: noticePeriodDays ? Number(noticePeriodDays) : null,
        preferredLocations: splitLocations(preferredLocations),
        profileLinks: links,
        voluntaryDisclosures,
        workAuthorization: workAuthorization.trim() || null,
      });
      applyProfile(saved);
      setSuccess(
        "Saved for this account. Apply for me will copy these answers into the next handoff pack. You still submit the application yourself.",
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "Your application answers could not be saved.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) {
    return <LoadingSkeleton variant="form" />;
  }

  return (
    <form className="space-y-5" onSubmit={(event) => void save(event)}>
      <Card className="overflow-hidden p-0">
        <div className="border-b border-line bg-gradient-to-br from-primary-soft/50 via-surface to-accent-soft/20 px-5 py-6 sm:px-7">
          <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-primary">
            Apply for me
          </p>
          <h2 className="mt-2 text-xl font-extrabold tracking-[-0.03em] text-foreground">
            Application answers
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            These are the questions employer portals typically ask (contact,
            eligibility, EEO self-ID, screening). Fill what you want reused.
            Blank means not provided. Decline is a complete answer. This is not
            inferred from your resume, and it is not a hiring score.
          </p>
          <p className="mt-3 text-xs font-semibold text-muted-strong">
            {answeredCount} answers filled across eligibility, pay, and{" "}
            {catalogFieldCount} catalog questions.
          </p>
        </div>
        <div className="space-y-4 px-5 py-5 sm:px-7">
          {failure && (
            <Alert title="Application answers not saved" tone="danger">
              {failure}
            </Alert>
          )}
          {success && (
            <Alert title="Saved to your account" tone="success">
              {success}
            </Alert>
          )}
          <Alert title="How this is stored" tone="info">
            Save writes an owner-scoped Application Profile for Apply for me.
            PostgreSQL remains the product source of truth; MongoDB stores a
            per-user copy when that store is enabled. Meridian does not scrape
            employer sites or auto-submit applications.
          </Alert>
        </div>
      </Card>

      <Card className="space-y-5 p-5 sm:p-7">
        <div>
          <h3 className="text-base font-extrabold text-foreground">
            Work authorization, pay, and locations
          </h3>
          <p className="mt-1 text-sm leading-6 text-muted">
            These first-class fields are copied into every Apply for me pack.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <FieldLabel htmlFor="workAuthorization">
              Work authorization
            </FieldLabel>
            <Select
              id="workAuthorization"
              onChange={(event) => setWorkAuthorization(event.target.value)}
              value={workAuthorization}
            >
              {withCurrentValue(
                WORK_AUTHORIZATION_OPTIONS,
                workAuthorization,
              ).map((option) => (
                <option key={option.value || "empty"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <TextField
            id="noticePeriodDays"
            label="Notice period (days)"
            max={730}
            min={0}
            onChange={(event) => setNoticePeriodDays(event.target.value)}
            type="number"
            value={noticePeriodDays}
          />
          <TextField
            id="compensationCurrency"
            label="Compensation currency"
            maxLength={3}
            minLength={3}
            onChange={(event) => setCompensationCurrency(event.target.value)}
            value={compensationCurrency}
          />
          <TextField
            id="compensationMin"
            label="Minimum compensation"
            min={0}
            onChange={(event) => setCompensationMin(event.target.value)}
            type="number"
            value={compensationMin}
          />
          <TextField
            id="compensationMax"
            label="Maximum compensation"
            min={0}
            onChange={(event) => setCompensationMax(event.target.value)}
            type="number"
            value={compensationMax}
          />
          <div className="sm:col-span-2">
            <TextField
              hint="Comma-separated. Example: Remote, Bengaluru, New York NY"
              id="preferredLocations"
              label="Preferred locations"
              onChange={(event) => setPreferredLocations(event.target.value)}
              value={preferredLocations}
            />
          </div>
        </div>
      </Card>

      <Card className="space-y-4 p-5 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-extrabold text-foreground">
              Profile links
            </h3>
            <p className="mt-1 text-sm leading-6 text-muted">
              URLs you want copied into application forms (portfolio, GitHub,
              publications).
            </p>
          </div>
          <Button onClick={addLink} type="button" variant="secondary">
            <Plus aria-hidden="true" className="size-4" />
            Add link
          </Button>
        </div>
        <div className="space-y-2">
          {profileLinks.length === 0 ? (
            <p className="text-sm text-muted">No links yet.</p>
          ) : (
            profileLinks.map((link, index) => (
              <div className="flex gap-2" key={index}>
                <TextField
                  aria-label="Link label"
                  id={`profile-link-label-${index}`}
                  label="Label"
                  onChange={(event) =>
                    updateLink(index, { label: event.target.value })
                  }
                  placeholder="Portfolio"
                  value={link.label}
                />
                <TextField
                  aria-label="Link URL"
                  hint="Must be an http(s) URL."
                  id={`profile-link-url-${index}`}
                  label="URL"
                  onChange={(event) =>
                    updateLink(index, { url: event.target.value })
                  }
                  placeholder="https://"
                  value={link.url}
                />
                <Button
                  aria-label={`Remove link ${index + 1}`}
                  className="mt-7"
                  onClick={() => removeLink(index)}
                  type="button"
                  variant="ghost"
                >
                  <Trash2 aria-hidden="true" className="size-4" />
                </Button>
              </div>
            ))
          )}
        </div>
      </Card>

      {QUESTIONNAIRE_SECTIONS.map((section) => (
        <Card
          className={
            section.sensitive
              ? "space-y-4 border-primary/20 p-5 sm:p-7"
              : "space-y-4 p-5 sm:p-7"
          }
          key={section.id}
        >
          <div>
            <h3 className="text-base font-extrabold text-foreground">
              {section.title}
            </h3>
            <p className="mt-1 text-sm leading-6 text-muted">
              {section.description}
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {section.fields.map((field) => (
              <div
                className={
                  field.kind === "text" && (field.maxLength ?? 0) > 200
                    ? "sm:col-span-2"
                    : undefined
                }
                key={field.key}
              >
                <FieldControl
                  field={field}
                  onChange={(value) => setAnswer(field.key, value)}
                  value={disclosureValue(answers, field.key)}
                />
              </div>
            ))}
          </div>
        </Card>
      ))}

      <Card className="space-y-4 p-5 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-extrabold text-foreground">
              Additional answers
            </h3>
            <p className="mt-1 text-sm leading-6 text-muted">
              Optional keys for a form that asks something this catalog does not
              list. Keys must be lowercase letters, numbers, or underscores.
            </p>
          </div>
          <Button onClick={addExtra} type="button" variant="secondary">
            <Plus aria-hidden="true" className="size-4" />
            Add answer
          </Button>
        </div>
        <div className="space-y-2">
          {extraRows.map((row, index) => (
            <div className="flex gap-2" key={index}>
              <TextField
                aria-label="Additional question key"
                id={`extra-key-${index}`}
                label="Key"
                onChange={(event) =>
                  updateExtra(index, { key: event.target.value })
                }
                placeholder="custom_question"
                value={row.key}
              />
              <TextField
                aria-label="Additional answer"
                id={`extra-value-${index}`}
                label="Answer"
                onChange={(event) =>
                  updateExtra(index, { value: event.target.value })
                }
                placeholder="Your answer"
                value={row.value}
              />
              <Button
                aria-label={`Remove additional answer ${index + 1}`}
                className="mt-7"
                onClick={() => removeExtra(index)}
                type="button"
                variant="ghost"
              >
                <Trash2 aria-hidden="true" className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <Card className="space-y-4 p-5 sm:p-7">
        <CheckboxField
          checked={acknowledged}
          description="Meridian stores what you enter for Apply for me packs. It does not infer disability, veteran status, race, color, or other protected characteristics from your career evidence."
          id="questionnaireAck"
          label="These answers are mine. Save them on this account for Apply for me."
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs leading-5 text-muted">
            You can leave questions blank. Saving overwrites the previous
            answers for this user.
          </p>
          <Button
            loading={saving}
            loadingLabel="Saving application answers…"
            type="submit"
          >
            <Save aria-hidden="true" className="size-4" />
            Save application answers
          </Button>
        </div>
      </Card>
    </form>
  );
}
