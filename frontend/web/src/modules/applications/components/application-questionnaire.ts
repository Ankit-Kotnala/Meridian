export type QuestionnaireOption = {
  label: string;
  value: string;
};

export type QuestionnaireField = {
  hint?: string;
  key: string;
  kind: "select" | "text";
  label: string;
  maxLength?: number;
  options?: readonly QuestionnaireOption[];
  placeholder?: string;
};

export type QuestionnaireSection = {
  description: string;
  fields: readonly QuestionnaireField[];
  id: string;
  sensitive?: boolean;
  title: string;
};

export const DECLINE_TO_IDENTIFY = "Decline to self-identify";
export const QUESTIONNAIRE_ACK_KEY = "questionnaire_ack";
export const QUESTIONNAIRE_ACK_VALUE = "acknowledged";

const NOT_PROVIDED: QuestionnaireOption = {
  label: "Not provided",
  value: "",
};

const DECLINE: QuestionnaireOption = {
  label: DECLINE_TO_IDENTIFY,
  value: DECLINE_TO_IDENTIFY,
};

function options(...labels: readonly string[]): QuestionnaireOption[] {
  return [
    NOT_PROVIDED,
    ...labels.map((label) => ({ label, value: label })),
    DECLINE,
  ];
}

function yesNo(): QuestionnaireOption[] {
  return options("Yes", "No");
}

export const WORK_AUTHORIZATION_OPTIONS: readonly QuestionnaireOption[] = [
  NOT_PROVIDED,
  {
    label: "Authorized to work in the United States; no sponsorship required",
    value: "Authorized to work in the United States; no sponsorship required",
  },
  {
    label:
      "Authorized to work in the United States; will require sponsorship now or later",
    value:
      "Authorized to work in the United States; will require sponsorship now or later",
  },
  {
    label: "Authorized to work in India; no sponsorship required",
    value: "Authorized to work in India; no sponsorship required",
  },
  {
    label: "Authorized to work in Canada; no sponsorship required",
    value: "Authorized to work in Canada; no sponsorship required",
  },
  {
    label: "Authorized to work in the United Kingdom; no sponsorship required",
    value: "Authorized to work in the United Kingdom; no sponsorship required",
  },
  {
    label: "Authorized to work in the European Union; no sponsorship required",
    value: "Authorized to work in the European Union; no sponsorship required",
  },
  {
    label: "Will require visa sponsorship for this role's country",
    value: "Will require visa sponsorship for this role's country",
  },
  {
    label: "Not authorized / not applicable",
    value: "Not authorized / not applicable",
  },
];

export const QUESTIONNAIRE_SECTIONS: readonly QuestionnaireSection[] = [
  {
    id: "contact",
    title: "Legal name and contact",
    description:
      "Most employer portals ask for a legal name, phone, and mailing address separately from your Career Record.",
    fields: [
      {
        key: "legal_first_name",
        kind: "text",
        label: "Legal first name",
        maxLength: 120,
      },
      {
        key: "legal_middle_name",
        kind: "text",
        label: "Legal middle name",
        maxLength: 120,
      },
      {
        key: "legal_last_name",
        kind: "text",
        label: "Legal last name",
        maxLength: 120,
      },
      {
        key: "preferred_name",
        kind: "text",
        label: "Preferred name",
        maxLength: 120,
      },
      {
        key: "phone",
        kind: "text",
        label: "Phone number",
        maxLength: 40,
        placeholder: "+1 555 0100",
      },
      {
        key: "phone_type",
        kind: "select",
        label: "Phone type",
        options: options("Mobile", "Home", "Work"),
      },
      {
        key: "address_line1",
        kind: "text",
        label: "Address line 1",
        maxLength: 200,
      },
      {
        key: "address_line2",
        kind: "text",
        label: "Address line 2",
        maxLength: 200,
      },
      { key: "city", kind: "text", label: "City", maxLength: 120 },
      {
        key: "region_state",
        kind: "text",
        label: "State / province / region",
        maxLength: 120,
      },
      {
        key: "postal_code",
        kind: "text",
        label: "Postal / ZIP code",
        maxLength: 32,
      },
      { key: "country", kind: "text", label: "Country", maxLength: 120 },
      {
        key: "linkedin_url",
        kind: "text",
        label: "LinkedIn URL",
        maxLength: 500,
        placeholder: "https://",
      },
      {
        key: "github_url",
        kind: "text",
        label: "GitHub URL",
        maxLength: 500,
        placeholder: "https://",
      },
      {
        key: "portfolio_url",
        kind: "text",
        label: "Portfolio URL",
        maxLength: 500,
        placeholder: "https://",
      },
      {
        key: "other_website_url",
        kind: "text",
        label: "Other website URL",
        maxLength: 500,
        placeholder: "https://",
      },
    ],
  },
  {
    id: "eligibility",
    title: "Work eligibility",
    description:
      "Work authorization, sponsorship, start date, clearance, and export-control questions that Greenhouse, Lever, Workday, and similar ATS forms ask before submit.",
    fields: [
      {
        key: "requires_visa_sponsorship",
        kind: "select",
        label: "Will you now or in the future require visa sponsorship?",
        options: yesNo(),
      },
      {
        key: "current_work_status",
        kind: "select",
        label: "Current work authorization status",
        options: options(
          "Citizen",
          "Permanent resident / green card",
          "Work visa (H-1B, L-1, TN, or similar)",
          "Employment authorization document (EAD)",
          "Student authorization (F-1 OPT/CPT, or similar)",
          "Other work authorization",
        ),
      },
      {
        key: "citizenship_status",
        kind: "select",
        label: "Citizenship (if asked)",
        options: options(
          "Citizen of the hiring country",
          "Dual citizen",
          "Not a citizen of the hiring country",
        ),
      },
      {
        key: "country_authorized_to_work",
        kind: "text",
        label: "Country you are authorized to work in",
        maxLength: 120,
      },
      {
        key: "canadian_work_status",
        kind: "select",
        label: "Canada work status (if asked)",
        options: options(
          "Canadian citizen",
          "Permanent resident",
          "Work permit",
          "Require a work permit",
        ),
      },
      {
        key: "uk_right_to_work",
        kind: "select",
        label: "United Kingdom right to work (if asked)",
        options: options(
          "Yes, I have the right to work in the UK",
          "No, I will need sponsorship",
        ),
      },
      {
        key: "over_18",
        kind: "select",
        label: "Are you 18 years of age or older?",
        options: yesNo(),
      },
      {
        key: "currently_employed",
        kind: "select",
        label: "Are you currently employed?",
        options: yesNo(),
      },
      {
        key: "serving_notice",
        kind: "select",
        label: "Are you currently serving a notice period?",
        options: yesNo(),
      },
      {
        key: "earliest_start_date",
        kind: "text",
        label: "Earliest start date",
        maxLength: 40,
        placeholder: "YYYY-MM-DD or Immediate",
      },
      {
        key: "willing_to_relocate",
        kind: "select",
        label: "Are you willing to relocate?",
        options: yesNo(),
      },
      {
        key: "relocation_preference",
        kind: "text",
        label: "Relocation regions (if any)",
        maxLength: 200,
      },
      {
        key: "travel_percentage",
        kind: "select",
        label: "Travel you can accept",
        options: options(
          "None",
          "Up to 10%",
          "Up to 25%",
          "Up to 50%",
          "More than 50%",
        ),
      },
      {
        key: "willing_to_travel_overnight",
        kind: "select",
        label: "Willing to travel overnight?",
        options: yesNo(),
      },
      {
        key: "security_clearance",
        kind: "select",
        label: "Security clearance",
        options: options(
          "No clearance",
          "Eligible / willing to be sponsored",
          "Confidential",
          "Secret",
          "Top Secret",
          "TS/SCI",
          "Other active clearance",
        ),
      },
      {
        key: "export_control_itar",
        kind: "select",
        label: "ITAR / export-control eligibility (if asked)",
        options: options(
          "I am a U.S. person as defined for export-control purposes",
          "I am not a U.S. person for export-control purposes",
          "Not applicable",
        ),
      },
      {
        key: "government_id_for_employment",
        kind: "select",
        label:
          "Can you present government ID for employment eligibility (I-9 / e-Verify)?",
        options: yesNo(),
      },
      {
        key: "passport_available",
        kind: "select",
        label: "Do you have a valid passport (if asked)?",
        options: yesNo(),
      },
    ],
  },
  {
    id: "compensation",
    title: "Compensation details",
    description:
      "Use the numbered fields above for expected pay. These extras cover period, equity, and jurisdictions that still ask about current pay — leave them blank where salary-history questions are banned.",
    fields: [
      {
        key: "compensation_period",
        kind: "select",
        label: "Compensation period",
        options: options(
          "Annual salary",
          "Monthly",
          "Hourly",
          "Daily / contract",
        ),
      },
      {
        key: "equity_consideration",
        kind: "select",
        label: "Open to equity as part of compensation?",
        options: yesNo(),
      },
      {
        key: "current_compensation_disclosure",
        kind: "select",
        label: "Current compensation (only if you choose to answer)",
        hint: "Many places ban salary-history questions. Decline is a complete answer.",
        options: options("I decline to provide salary history"),
      },
    ],
  },
  {
    id: "screening",
    title: "Education and screening",
    description:
      "Education, experience band, background checks, licenses, and languages that screening forms typically collect.",
    fields: [
      {
        key: "highest_education",
        kind: "select",
        label: "Highest education completed",
        options: options(
          "High school / secondary",
          "Some college",
          "Associate degree",
          "Bachelor’s degree",
          "Master’s degree",
          "Doctorate / professional degree",
          "Trade / vocational certificate",
        ),
      },
      {
        key: "field_of_study",
        kind: "text",
        label: "Field of study",
        maxLength: 160,
      },
      {
        key: "graduation_year",
        kind: "text",
        label: "Graduation year",
        maxLength: 4,
        placeholder: "YYYY",
      },
      {
        key: "years_of_experience",
        kind: "select",
        label: "Years of relevant experience",
        options: options(
          "Less than 1 year",
          "1–2 years",
          "3–5 years",
          "6–8 years",
          "9–12 years",
          "13+ years",
        ),
      },
      {
        key: "willing_background_check",
        kind: "select",
        label: "Willing to complete a background check if an offer is made?",
        options: yesNo(),
      },
      {
        key: "willing_drug_test",
        kind: "select",
        label: "Willing to complete a drug test if required by the role?",
        options: yesNo(),
      },
      {
        key: "professional_license",
        kind: "text",
        label: "Professional licenses or certifications (if asked)",
        maxLength: 400,
      },
      {
        key: "drivers_license",
        kind: "select",
        label: "Valid driver’s license (if the role requires driving)",
        options: yesNo(),
      },
      {
        key: "languages_spoken",
        kind: "text",
        label: "Languages",
        maxLength: 400,
        placeholder: "English (fluent), Hindi (fluent)",
      },
    ],
  },
  {
    id: "schedule",
    title: "Schedule and work arrangement",
    description:
      "Remote/hybrid, shifts, overtime, and hours — common on hourly, operations, and hybrid professional forms.",
    fields: [
      {
        key: "work_arrangement",
        kind: "select",
        label: "Preferred work arrangement",
        options: options(
          "On-site",
          "Hybrid",
          "Remote",
          "Flexible / no preference",
        ),
      },
      {
        key: "remote_work_percentage",
        kind: "select",
        label: "Remote work you can do",
        options: options(
          "On-site only",
          "Hybrid",
          "Fully remote",
          "No preference",
        ),
      },
      {
        key: "shift_preference",
        kind: "select",
        label: "Shift preference",
        options: options(
          "Day",
          "Evening",
          "Night",
          "Rotating",
          "No preference",
        ),
      },
      {
        key: "overtime_availability",
        kind: "select",
        label: "Available for overtime if required?",
        options: yesNo(),
      },
      {
        key: "weekend_availability",
        kind: "select",
        label: "Available on weekends if required?",
        options: yesNo(),
      },
      {
        key: "expected_hours",
        kind: "select",
        label: "Expected hours",
        options: options(
          "Full-time",
          "Part-time",
          "Contract / temporary",
          "Internship",
        ),
      },
    ],
  },
  {
    id: "eeo",
    title: "Voluntary EEO and self-identification",
    sensitive: true,
    description:
      "U.S. employers often collect these under EEO-1, VEVRAA, and Section 503. They are voluntary. Decline is a valid answer. Meridian never infers sex, race, color, veteran status, disability, or similar traits from your resume.",
    fields: [
      {
        key: "eeo_sex",
        kind: "select",
        label: "Sex (EEO-1)",
        options: options("Male", "Female"),
      },
      {
        key: "gender_identity",
        kind: "select",
        label: "Gender identity (if asked)",
        options: options(
          "Man",
          "Woman",
          "Non-binary",
          "Self-describe / another identity",
        ),
      },
      {
        key: "pronouns",
        kind: "select",
        label: "Pronouns (if asked)",
        options: options("he/him", "she/her", "they/them", "Use my name"),
      },
      {
        key: "hispanic_or_latino",
        kind: "select",
        label: "Hispanic or Latino (EEO-1)",
        options: yesNo(),
      },
      {
        key: "race_ethnicity",
        kind: "select",
        label: "Race / ethnicity (EEO-1)",
        options: options(
          "White",
          "Black or African American",
          "Asian",
          "American Indian or Alaska Native",
          "Native Hawaiian or Other Pacific Islander",
          "Two or more races",
        ),
      },
      {
        key: "color",
        kind: "select",
        label: "Color (if an older form asks separately from race)",
        options: options("White", "Black", "Other"),
      },
      {
        key: "national_origin",
        kind: "text",
        label: "National origin (if asked)",
        maxLength: 120,
        hint: "Optional. Decline by leaving this blank or typing that you decline.",
      },
      {
        key: "veteran_status",
        kind: "select",
        label: "Veteran status (VEVRAA)",
        options: options(
          "I identify as one or more of the classifications of a protected veteran",
          "I am not a protected veteran",
        ),
      },
      {
        key: "veteran_classification",
        kind: "select",
        label:
          "Protected veteran classification (if you identified as a veteran)",
        options: options(
          "Disabled veteran",
          "Recently separated veteran",
          "Active duty wartime or campaign badge veteran",
          "Armed Forces service medal veteran",
        ),
      },
      {
        key: "disability_status",
        kind: "select",
        label: "Disability status (Section 503)",
        options: options(
          "Yes, I have a disability, or have a history/record of having a disability",
          "No, I do not have a disability and have no history of a disability",
        ),
      },
      {
        key: "disability_accommodation",
        kind: "select",
        label:
          "Need a reasonable accommodation for the application or interview?",
        options: yesNo(),
      },
      {
        key: "sexual_orientation",
        kind: "select",
        label: "Sexual orientation (if asked)",
        options: options(
          "Heterosexual / straight",
          "Gay or lesbian",
          "Bisexual",
          "Another orientation",
        ),
      },
      {
        key: "marital_status",
        kind: "select",
        label: "Marital status (if asked)",
        options: options(
          "Single",
          "Married",
          "Domestic partnership",
          "Divorced",
          "Widowed",
        ),
      },
      {
        key: "religion",
        kind: "select",
        label: "Religion (if asked)",
        options: options(
          "No religious affiliation",
          "I decline to specify a religion",
        ),
      },
      {
        key: "indigenous_identity",
        kind: "select",
        label: "Indigenous identity (Canada employment equity, if asked)",
        options: yesNo(),
      },
      {
        key: "visible_minority",
        kind: "select",
        label: "Visible minority (Canada employment equity, if asked)",
        options: yesNo(),
      },
    ],
  },
  {
    id: "history",
    title: "Application history and conflicts",
    description:
      "How you heard about the role, prior applications, referrals, relatives, non-competes, and other conflict questions.",
    fields: [
      {
        key: "how_heard",
        kind: "select",
        label: "How did you hear about this company / role type?",
        options: options(
          "Company careers site",
          "Job board",
          "LinkedIn",
          "Employee referral",
          "Recruiter",
          "University / campus",
          "Career fair",
          "Other",
        ),
      },
      {
        key: "previously_applied",
        kind: "select",
        label: "Have you applied to this employer before?",
        options: yesNo(),
      },
      {
        key: "former_employee",
        kind: "select",
        label: "Have you ever been employed by this employer?",
        options: yesNo(),
      },
      {
        key: "referral_name",
        kind: "text",
        label: "Referral name (if any)",
        maxLength: 160,
      },
      {
        key: "relative_at_company",
        kind: "select",
        label: "Do you have a relative or close relationship at the employer?",
        options: yesNo(),
      },
      {
        key: "noncompete_obligation",
        kind: "select",
        label: "Are you subject to a non-compete or similar restriction?",
        options: yesNo(),
      },
      {
        key: "conflict_of_interest",
        kind: "select",
        label: "Do you have a conflict of interest to disclose?",
        options: yesNo(),
      },
      {
        key: "criminal_history_disclosure",
        kind: "select",
        label: "Criminal history (only if a lawful form asks)",
        hint: "Ban-the-box and similar laws often forbid this until later. Decline unless you choose to answer a specific employer form.",
        options: options(
          "I decline to answer here; I will answer only on a lawful employer form",
        ),
      },
      {
        key: "covid_vaccination_status",
        kind: "select",
        label: "COVID-19 vaccination (if still asked)",
        options: options("Vaccinated", "Not vaccinated", "Not applicable"),
      },
    ],
  },
];

export const CATALOG_DISCLOSURE_KEYS: ReadonlySet<string> = new Set(
  QUESTIONNAIRE_SECTIONS.flatMap((section) =>
    section.fields.map((field) => field.key),
  ),
);

export const MAX_VOLUNTARY_DISCLOSURES = 100;

export function withCurrentValue(
  options: readonly QuestionnaireOption[],
  value: string,
): QuestionnaireOption[] {
  if (!value || options.some((option) => option.value === value)) {
    return [...options];
  }
  return [...options, { label: value, value }];
}

export function asHttpUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}
