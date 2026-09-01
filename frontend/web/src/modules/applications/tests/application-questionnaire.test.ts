import { describe, expect, it } from "vitest";

import {
  CATALOG_DISCLOSURE_KEYS,
  QUESTIONNAIRE_ACK_KEY,
  QUESTIONNAIRE_SECTIONS,
  asHttpUrl,
  withCurrentValue,
} from "../components/application-questionnaire";

const KEY = /^[a-z0-9_]{3,80}$/;

describe("application questionnaire catalog", () => {
  it("uses unique snake_case keys that fit the Application Profile contract", () => {
    const keys = QUESTIONNAIRE_SECTIONS.flatMap((section) =>
      section.fields.map((field) => field.key),
    );
    expect(keys).toHaveLength(CATALOG_DISCLOSURE_KEYS.size);
    expect(keys.length).toBeGreaterThanOrEqual(70);
    expect(keys).toEqual([...new Set(keys)]);
    expect(keys.every((key) => KEY.test(key))).toBe(true);
    expect(KEY.test(QUESTIONNAIRE_ACK_KEY)).toBe(true);
    expect(CATALOG_DISCLOSURE_KEYS.has("disability_status")).toBe(true);
    expect(CATALOG_DISCLOSURE_KEYS.has("veteran_status")).toBe(true);
    expect(CATALOG_DISCLOSURE_KEYS.has("race_ethnicity")).toBe(true);
    expect(CATALOG_DISCLOSURE_KEYS.has("color")).toBe(true);
  });

  it("keeps a saved value that is not in the catalog options", () => {
    const options = withCurrentValue(
      [{ label: "Not provided", value: "" }],
      "prefer_not_to_say",
    );
    expect(options.at(-1)).toEqual({
      label: "prefer_not_to_say",
      value: "prefer_not_to_say",
    });
  });

  it("prefixes profile links with https when a scheme is missing", () => {
    expect(asHttpUrl("linkedin.com/in/example")).toBe(
      "https://linkedin.com/in/example",
    );
    expect(asHttpUrl("https://example.test/x")).toBe("https://example.test/x");
  });

  it("keeps every select on a Not provided / decline path", () => {
    for (const section of QUESTIONNAIRE_SECTIONS) {
      for (const field of section.fields) {
        if (field.kind !== "select" || !field.options) continue;
        expect(field.options[0]).toEqual({
          label: "Not provided",
          value: "",
        });
        expect(
          field.options.some(
            (option) => option.value === "Decline to self-identify",
          ),
        ).toBe(true);
      }
    }
  });
});
