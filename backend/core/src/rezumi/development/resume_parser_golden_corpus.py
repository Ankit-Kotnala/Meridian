"""Golden, hand-labeled corpus for `rezumi.development.eval_resume_parser`.

Each case is deliberately small and focused on one real-world diversity gap
identified before this corpus existed (see the parser-accuracy plan): plain
baseline, comma-separated vs. pipe-separated headers, numeric/slash date
formats, a concurrent-role case, a career-gap case, an unusual/hyphenated
name, a non-English (Spanish) case, single-line contact headers, day-precision
dates, visible bullet markers, multi-line role headers, repeated
achievements, location vs. field of study, token-classified employer/title
order, contact location, and locale open-ended dates. This is a starting
corpus, not an exhaustive one — extend it as new real-world failure modes
are found.
"""

from __future__ import annotations

from rezumi.development.eval_resume_parser import GoldenCase, GoldenSection
from rezumi.modules.resume_health.domain import BlockKind, SectionKind, SemanticEntityKind

GOLDEN_CORPUS: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="baseline: comma-separated header, single role",
        sections=(
            GoldenSection(
                kind=SectionKind.CONTACT,
                blocks=(
                    (BlockKind.PARAGRAPH, "Jordan Lee"),
                    (BlockKind.PARAGRAPH, "jordan.lee@example.test | +1 415-555-0182"),
                ),
            ),
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (
                        BlockKind.PARAGRAPH,
                        "Senior Backend Engineer, Acme Corp, Remote",
                    ),
                    (BlockKind.PARAGRAPH, "Jan 2021 - Present"),
                    (BlockKind.BULLET, "Led migration to a service mesh."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.CONTACT: (
                {
                    "name": "Jordan Lee",
                    "email": "jordan.lee@example.test",
                    "phone": "+1 415-555-0182",
                },
            ),
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Senior Backend Engineer",
                    "employer": "Acme Corp",
                    "location": "Remote",
                    "start_date": "Jan 2021",
                    "end_date": "Present",
                    "achievement": "Led migration to a service mesh.",
                },
            ),
        },
    ),
    GoldenCase(
        name="pipe-separated header",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Acme Corp | Senior Backend Engineer | Remote"),
                    (BlockKind.PARAGRAPH, "Jan 2021 - Present"),
                    (BlockKind.BULLET, "Led migration to a service mesh."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "employer": "Acme Corp",
                    "title": "Senior Backend Engineer",
                    "location": "Remote",
                    "start_date": "Jan 2021",
                    "end_date": "Present",
                    "achievement": "Led migration to a service mesh.",
                },
            ),
        },
    ),
    GoldenCase(
        name="numeric slash dates",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Product Manager, Globex Inc, Austin TX"),
                    (BlockKind.PARAGRAPH, "03/2019 - 11/2022"),
                    (BlockKind.BULLET, "Shipped three major releases."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Product Manager",
                    "employer": "Globex Inc",
                    "location": "Austin TX",
                    "start_date": "03/2019",
                    "end_date": "11/2022",
                    "achievement": "Shipped three major releases.",
                },
            ),
        },
    ),
    GoldenCase(
        name="concurrent roles at different employers",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Consultant, Freelance, Remote"),
                    (BlockKind.PARAGRAPH, "Jun 2022 - Present"),
                    (BlockKind.BULLET, "Advised three startups on platform architecture."),
                    (BlockKind.PARAGRAPH, "Board Member, Nonprofit Housing Trust, Remote"),
                    (BlockKind.PARAGRAPH, "Jun 2022 - Present"),
                    (BlockKind.BULLET, "Chaired the technology committee."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Consultant",
                    "employer": "Freelance",
                    "location": "Remote",
                    "start_date": "Jun 2022",
                    "end_date": "Present",
                    "achievement": "Advised three startups on platform architecture.",
                },
                {
                    "title": "Board Member",
                    "employer": "Nonprofit Housing Trust",
                    "location": "Remote",
                    "start_date": "Jun 2022",
                    "end_date": "Present",
                    "achievement": "Chaired the technology committee.",
                },
            ),
        },
    ),
    GoldenCase(
        name="career gap between two roles",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Software Engineer, Initech, Remote"),
                    (BlockKind.PARAGRAPH, "2017 - 2019"),
                    (BlockKind.BULLET, "Built the billing service."),
                    (BlockKind.PARAGRAPH, "Software Engineer, Umbrella LLC, Remote"),
                    (BlockKind.PARAGRAPH, "2022 - Present"),
                    (BlockKind.BULLET, "Rebuilt the notifications pipeline."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Software Engineer",
                    "employer": "Initech",
                    "location": "Remote",
                    "start_date": "2017",
                    "end_date": "2019",
                    "achievement": "Built the billing service.",
                },
                {
                    "title": "Software Engineer",
                    "employer": "Umbrella LLC",
                    "location": "Remote",
                    "start_date": "2022",
                    "end_date": "Present",
                    "achievement": "Rebuilt the notifications pipeline.",
                },
            ),
        },
    ),
    GoldenCase(
        name="hyphenated name with middle initial",
        sections=(
            GoldenSection(
                kind=SectionKind.CONTACT,
                blocks=((BlockKind.PARAGRAPH, "Maria J. Alvarez-Nakamura"),),
            ),
        ),
        expected={
            SemanticEntityKind.CONTACT: ({"name": "Maria J. Alvarez-Nakamura"},),
        },
    ),
    GoldenCase(
        name="education with location rather than a mislabeled field",
        sections=(
            GoldenSection(
                kind=SectionKind.EDUCATION,
                blocks=(
                    (
                        BlockKind.PARAGRAPH,
                        "B.S. in Computer Science, University of Texas, Austin TX",
                    ),
                    (BlockKind.PARAGRAPH, "Aug 2013 - May 2017"),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EDUCATION: (
                {
                    "degree": "B.S. in Computer Science",
                    "institution": "University of Texas",
                    "location": "Austin TX",
                    "start_date": "Aug 2013",
                    "end_date": "May 2017",
                },
            ),
        },
    ),
    GoldenCase(
        name="certification with issued and expiry dates",
        sections=(
            GoldenSection(
                kind=SectionKind.CERTIFICATIONS,
                blocks=(
                    (
                        BlockKind.PARAGRAPH,
                        "AWS Certified Solutions Architect, Amazon Web Services",
                    ),
                    (BlockKind.PARAGRAPH, "Issued Mar 2022, Expires Mar 2025"),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.CERTIFICATION: (
                {
                    "name": "AWS Certified Solutions Architect",
                    "issuer": "Amazon Web Services",
                    "issued_date": "Mar 2022",
                    "expires_date": "Mar 2025",
                },
            ),
        },
    ),
    GoldenCase(
        name="skills list with compound slash terms",
        sections=(
            GoldenSection(
                kind=SectionKind.SKILLS,
                blocks=((BlockKind.PARAGRAPH, "CI/CD, TCP/IP, Python, A/B testing"),),
            ),
        ),
        expected={
            SemanticEntityKind.SKILL: (
                {"name": "CI/CD"},
                {"name": "TCP/IP"},
                {"name": "Python"},
                {"name": "A/B testing"},
            ),
        },
    ),
    GoldenCase(
        name="non-English (Spanish) contact and role",
        sections=(
            GoldenSection(
                kind=SectionKind.CONTACT,
                blocks=((BlockKind.PARAGRAPH, "Carmen Ruiz"),),
            ),
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Gerente de Producto, Empresa Solaris, Madrid"),
                    (BlockKind.PARAGRAPH, "2020 - Present"),
                    (BlockKind.BULLET, "Lanzó tres productos nuevos."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.CONTACT: ({"name": "Carmen Ruiz"},),
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Gerente de Producto",
                    "employer": "Empresa Solaris",
                    "location": "Madrid",
                    "start_date": "2020",
                    "end_date": "Present",
                    "achievement": "Lanzó tres productos nuevos.",
                },
            ),
        },
    ),
    GoldenCase(
        name="single-line contact header",
        sections=(
            GoldenSection(
                kind=SectionKind.CONTACT,
                blocks=(
                    (
                        BlockKind.PARAGRAPH,
                        "Priya Raman | priya.raman@example.test | +91 98765 43210",
                    ),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.CONTACT: (
                {
                    "name": "Priya Raman",
                    "email": "priya.raman@example.test",
                    "phone": "+91 98765 43210",
                },
            ),
        },
    ),
    GoldenCase(
        name="multiline consecutive roles with repeated achievements",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Senior Engineer"),
                    (BlockKind.PARAGRAPH, "Acme Corp"),
                    (BlockKind.PARAGRAPH, "Jan 2020 - Dec 2022"),
                    (BlockKind.BULLET, "Built the first platform."),
                    (BlockKind.BULLET, "Improved deployment safety."),
                    (BlockKind.PARAGRAPH, "Staff Engineer"),
                    (BlockKind.PARAGRAPH, "Globex Inc"),
                    (BlockKind.PARAGRAPH, "Jan 2023 - Present"),
                    (BlockKind.BULLET, "Scaled the second platform."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Senior Engineer",
                    "employer": "Acme Corp",
                    "start_date": "Jan 2020",
                    "end_date": "Dec 2022",
                    "achievement": (
                        "Built the first platform.",
                        "Improved deployment safety.",
                    ),
                },
                {
                    "title": "Staff Engineer",
                    "employer": "Globex Inc",
                    "start_date": "Jan 2023",
                    "end_date": "Present",
                    "achievement": "Scaled the second platform.",
                },
            ),
        },
    ),
    GoldenCase(
        name="day-precision dates and visible bullet marker",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (
                        BlockKind.PARAGRAPH,
                        "Engineer, Northwind Labs, Jan. 5, 2020 - 2024-06-30",
                    ),
                    (BlockKind.BULLET, "\u2022 Led the migration."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Engineer",
                    "employer": "Northwind Labs",
                    "start_date": "Jan. 5, 2020",
                    "end_date": "2024-06-30",
                    "achievement": "Led the migration.",
                },
            ),
        },
    ),
    GoldenCase(
        name="employer-first comma header classified by token, not position",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Acme Corp, Senior Engineer, Remote"),
                    (BlockKind.PARAGRAPH, "Jan 2021 - Present"),
                    (BlockKind.BULLET, "Shipped the billing rewrite."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Senior Engineer",
                    "employer": "Acme Corp",
                    "location": "Remote",
                    "start_date": "Jan 2021",
                    "end_date": "Present",
                    "achievement": "Shipped the billing rewrite.",
                },
            ),
        },
    ),
    GoldenCase(
        name="contact location on the same line as email",
        sections=(
            GoldenSection(
                kind=SectionKind.CONTACT,
                blocks=(
                    (
                        BlockKind.PARAGRAPH,
                        "Alex Rivera | alex.rivera@example.test | Portland, OR",
                    ),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.CONTACT: (
                {
                    "name": "Alex Rivera",
                    "email": "alex.rivera@example.test",
                    "location": "Portland, OR",
                },
            ),
        },
    ),
    GoldenCase(
        name="ambiguous numeric day/month stays a date without pretending a locale",
        sections=(
            GoldenSection(
                kind=SectionKind.EXPERIENCE,
                blocks=(
                    (BlockKind.PARAGRAPH, "Analyst, Umbrella LLC, Remote"),
                    (BlockKind.PARAGRAPH, "03/04/2020 - Presente"),
                    (BlockKind.BULLET, "Documented the fictional control plane."),
                ),
            ),
        ),
        expected={
            SemanticEntityKind.EXPERIENCE: (
                {
                    "title": "Analyst",
                    "employer": "Umbrella LLC",
                    "location": "Remote",
                    "start_date": "03/04/2020",
                    "end_date": "Presente",
                    "achievement": "Documented the fictional control plane.",
                },
            ),
        },
    ),
)
