"""Seed the curated role-roadmap library (Phase 13).

This content is self-authored and versioned — never scraped from roadmap.sh
or any other third-party roadmap site (their licenses do not permit
reproducing their content elsewhere; see ADR 0019 §5 and the plan that
introduced this feature). It intentionally covers a starting set of common
tech/product roles, not every possible job title — the document shape below
makes adding more roles a matter of appending an entry, not a schema change.

Run with:

    uv run python -m rezumi.development.seed_role_roadmaps

or, against the running local stack:

    docker compose exec worker python3 -m rezumi.development.seed_role_roadmaps
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient

from rezumi.foundation.config.mongodb import MongoOptions

ROADMAP_VERSION = "role-roadmaps/2026-08-23.1"

# Each skill entry: name (matched against a role_readiness gap label),
# why (one sentence on why it matters), howToStart (one concrete first step).
ROLE_ROADMAPS: list[dict[str, Any]] = [
    {
        "roleSlug": "software-engineer",
        "title": "Software Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Data structures and algorithms",
                        "why": "Most engineering interviews and day-to-day debugging assume fluency with core data structures and their time/space tradeoffs.",
                        "howToStart": "Pick one structure a week (arrays, hash maps, trees, graphs) and re-implement it from scratch before using a library version.",
                    },
                    {
                        "name": "Version control",
                        "why": "Git is the shared language every engineering team uses to collaborate on and review changes safely.",
                        "howToStart": "Practice a full branch → commit → pull request → review cycle on a personal project before doing it on a team.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Testing",
                        "why": "Automated tests are what let a team change code confidently without re-verifying everything by hand.",
                        "howToStart": "Add unit tests to one existing personal project until every core function has at least one passing and one failing-case test.",
                    },
                    {
                        "name": "System design",
                        "why": "Beyond entry level, engineers are expected to reason about how services, data, and failure modes fit together, not just write functions.",
                        "howToStart": "Sketch the architecture of a product you use daily (queues, databases, caches) before reading how it's actually built, then compare.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Distributed systems",
                        "why": "Production systems at scale run across many machines, and that introduces failure modes single-machine code never has to handle.",
                        "howToStart": "Read one real postmortem of a distributed outage and identify which failure mode (network partition, retry storm, etc.) caused it.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "frontend-engineer",
        "title": "Frontend Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "HTML and CSS",
                        "why": "Every UI framework compiles down to HTML and CSS, and layout/accessibility bugs are easiest to fix with a solid grasp of the underlying model.",
                        "howToStart": "Rebuild one existing webpage's layout using only semantic HTML and CSS Grid/Flexbox, no framework.",
                    },
                    {
                        "name": "JavaScript / TypeScript fundamentals",
                        "why": "Frameworks change; the language underneath (closures, async, the event loop) stays the foundation of debugging real issues.",
                        "howToStart": "Write a small app with no framework — just fetch, DOM APIs, and vanilla JS/TS — to see what a framework is actually doing for you.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Component architecture",
                        "why": "Most production frontend work is organizing state and props across a component tree cleanly, not writing new components.",
                        "howToStart": "Take an existing single large component and split it into 3-4 smaller ones with clearly separated responsibilities.",
                    },
                    {
                        "name": "Accessibility",
                        "why": "Accessible UI is both a legal requirement in many contexts and simply usable by more people — it is not optional polish.",
                        "howToStart": "Navigate one real page you built using only a keyboard and a screen reader, and fix whatever breaks.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Performance optimization",
                        "why": "Render performance and bundle size directly affect real user retention, especially on slower devices and networks.",
                        "howToStart": "Run a Lighthouse or Web Vitals audit on a real page you shipped and fix the single largest flagged issue.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "backend-engineer",
        "title": "Backend Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Relational databases",
                        "why": "Most backend systems are ultimately shaped by how their data is modeled and queried.",
                        "howToStart": "Design a normalized schema for a small real-world domain (e.g. a library catalog) and write the queries a real app would need.",
                    },
                    {
                        "name": "API design",
                        "why": "A backend engineer's job is largely defining and maintaining contracts other systems depend on.",
                        "howToStart": "Design a REST or RPC API for one feature, write its contract first, then implement against that contract.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Caching",
                        "why": "Caching is one of the most common ways backend systems meet latency and load requirements without redesigning everything.",
                        "howToStart": "Add a cache layer (even an in-memory one) in front of one expensive query in a personal project and measure the difference.",
                    },
                    {
                        "name": "Message queues",
                        "why": "Queues decouple slow or unreliable work from the request path, which is essential once a system has real traffic.",
                        "howToStart": "Move one synchronous, slow operation in a personal project (like sending an email) behind a queue and a worker.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Scalability",
                        "why": "Designing for horizontal scale changes assumptions about state, consistency, and coordination.",
                        "howToStart": "Take a single-instance service you've built and identify every place it assumes only one instance is running.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "full-stack-engineer",
        "title": "Full-Stack Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "End-to-end feature ownership",
                        "why": "Full-stack roles are defined by owning a feature from database to UI, not by any single technology.",
                        "howToStart": "Build one small feature completely solo — schema, API, and UI — instead of only ever touching one layer.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "API contracts across the stack",
                        "why": "Full-stack engineers are the ones who feel the pain first when frontend and backend assumptions about a contract drift apart.",
                        "howToStart": "Add a typed contract (OpenAPI, GraphQL schema, or shared types) between your frontend and backend on one project.",
                    },
                    {
                        "name": "Deployment basics",
                        "why": "Shipping a full-stack feature means understanding how both the app and the data layer actually get deployed.",
                        "howToStart": "Deploy one small full-stack project yourself end-to-end, including the database, without relying on a platform's defaults.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Cross-layer performance debugging",
                        "why": "The hardest full-stack bugs span layers — a slow page can be a frontend, network, or database problem.",
                        "howToStart": "Trace one real slow request from browser network tab through to the exact database query causing it.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "data-scientist",
        "title": "Data Scientist",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Statistics",
                        "why": "Every model and A/B test result depends on correctly understanding uncertainty, significance, and bias.",
                        "howToStart": "Re-derive and explain, in your own words, the difference between correlation and causation using a real dataset.",
                    },
                    {
                        "name": "Data wrangling",
                        "why": "The majority of real data science time is spent cleaning and reshaping data, not modeling it.",
                        "howToStart": "Take a genuinely messy public dataset and get it into a clean, analysis-ready shape before doing anything else with it.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Experiment design",
                        "why": "Knowing how to design a valid A/B test is what turns a data scientist's work into a trustworthy business decision.",
                        "howToStart": "Design (on paper) a full A/B test for a real product change, including sample size and success metric, before ever running one.",
                    },
                    {
                        "name": "Model evaluation",
                        "why": "Picking the right metric and validation strategy matters more than picking the fanciest model.",
                        "howToStart": "Take one model you've trained and evaluate it with at least three different metrics to see where they disagree.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Communicating results to non-technical stakeholders",
                        "why": "A correct analysis that isn't understood or trusted by decision-makers doesn't change anything.",
                        "howToStart": "Rewrite one of your own technical findings as a one-paragraph summary a non-technical manager could act on.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "data-engineer",
        "title": "Data Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "SQL at scale",
                        "why": "Data engineers write and optimize queries over datasets far larger than typical application databases.",
                        "howToStart": "Take a slow query against a large public dataset and improve it using indexing or query restructuring, then measure the difference.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Data pipelines (ETL/ELT)",
                        "why": "Reliable, observable pipelines are the backbone every downstream analytics and ML system depends on.",
                        "howToStart": "Build one small pipeline that extracts, transforms, and loads real data on a schedule, with basic failure alerting.",
                    },
                    {
                        "name": "Data modeling for analytics",
                        "why": "Analytics workloads need different modeling tradeoffs (denormalization, partitioning) than transactional systems.",
                        "howToStart": "Take a normalized transactional schema and redesign it as a star schema for reporting queries.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Data quality and observability",
                        "why": "Bad data silently breaks every downstream decision, so catching it early is as important as moving it fast.",
                        "howToStart": "Add automated data-quality checks (null rates, schema drift) to one pipeline you already run.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "ml-engineer",
        "title": "Machine Learning Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Applied machine learning fundamentals",
                        "why": "ML engineering builds on top of core ML concepts (bias/variance, overfitting) even when the job is mostly infrastructure.",
                        "howToStart": "Train and evaluate one simple model end-to-end on a public dataset before touching any deployment tooling.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Model deployment and serving",
                        "why": "A model that only runs in a notebook delivers no value; ML engineering is about getting models into production reliably.",
                        "howToStart": "Wrap one trained model behind a simple API endpoint and load-test it to see where it breaks.",
                    },
                    {
                        "name": "ML pipeline reproducibility",
                        "why": "Without versioned data, code, and models, a result that worked once often can't be reproduced or trusted later.",
                        "howToStart": "Add data and model versioning to one existing training script so a past result can be exactly reproduced.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Model monitoring and drift detection",
                        "why": "Model performance degrades silently as real-world data shifts away from training data.",
                        "howToStart": "Set up a basic monitor comparing live prediction distributions against training-time distributions for one deployed model.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "devops-sre-engineer",
        "title": "DevOps / Site Reliability Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Linux and networking basics",
                        "why": "Nearly all infrastructure work assumes comfort diagnosing systems at the OS and network layer.",
                        "howToStart": "Debug one real connectivity or performance issue using only command-line tools (curl, dig, netstat, top).",
                    },
                    {
                        "name": "Infrastructure as code",
                        "why": "Manually configured infrastructure can't be reliably reproduced, audited, or rolled back.",
                        "howToStart": "Recreate one manually-configured piece of infrastructure you run using a tool like Terraform or Pulumi.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "CI/CD pipelines",
                        "why": "Fast, reliable deployment pipelines are what let a team ship changes safely and often.",
                        "howToStart": "Build a pipeline that runs tests and deploys a small app automatically on every merge to main.",
                    },
                    {
                        "name": "Monitoring and alerting",
                        "why": "You can't operate a system reliably if you can't see when it's degrading before users notice.",
                        "howToStart": "Instrument one service with basic metrics (latency, error rate) and set an alert threshold for each.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Incident response",
                        "why": "How a team responds to an outage — not just whether one happens — determines the real user impact.",
                        "howToStart": "Write a runbook for one service's most likely failure mode before it actually happens, then run a tabletop drill against it.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "product-manager",
        "title": "Product Manager",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "User research",
                        "why": "Product decisions grounded in real user problems consistently outperform decisions grounded in internal opinion.",
                        "howToStart": "Run five short user interviews about one specific problem and write up the actual quotes, not just your summary of them.",
                    },
                    {
                        "name": "Writing a product spec",
                        "why": "A clear spec is what lets engineering, design, and stakeholders build the same thing without constant re-clarification.",
                        "howToStart": "Write a one-page spec for a real feature idea that states the problem, the non-goals, and how you'd know it worked.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Prioritization frameworks",
                        "why": "Every roadmap has more good ideas than capacity, so a defensible way to say no is a core skill, not a nice-to-have.",
                        "howToStart": "Score your current backlog with one framework (RICE, ICE, or similar) and see which of your instincts it confirms or challenges.",
                    },
                    {
                        "name": "Metrics and analytics",
                        "why": "A PM who can't read their own product's data is dependent on others to tell them if a decision worked.",
                        "howToStart": "Pick one feature you shipped and define, then pull, the single metric that would tell you if it succeeded.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Cross-functional stakeholder alignment",
                        "why": "Most PM failures are not bad ideas — they're good ideas that lost alignment with engineering, design, or leadership along the way.",
                        "howToStart": "Before your next roadmap review, get informal buy-in from each function individually so the group meeting has no surprises.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "product-designer",
        "title": "Product Designer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Interaction design fundamentals",
                        "why": "Visual polish means little if the underlying flow confuses users or fights how they actually think.",
                        "howToStart": "Redesign one confusing flow from a product you use, focused only on reducing steps and ambiguity, not visuals.",
                    },
                    {
                        "name": "Design tools fluency",
                        "why": "Fast, clean execution in your tool of choice (e.g. Figma) is what lets design thinking translate into shippable specs.",
                        "howToStart": "Rebuild one existing screen from scratch in your design tool using components and auto-layout, not one-off shapes.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "User research for design",
                        "why": "Designers who validate assumptions with real users catch usability problems long before expensive engineering work starts.",
                        "howToStart": "Usability-test one of your own designs with 3-5 people before it ships, and note every point of hesitation.",
                    },
                    {
                        "name": "Design systems",
                        "why": "A shared design system is what keeps a growing product visually and behaviorally consistent across teams.",
                        "howToStart": "Audit one product area for inconsistent components (buttons, spacing) and propose a single shared version.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Design-to-engineering handoff",
                        "why": "A design that engineering can't accurately implement doesn't ship as intended, no matter how good the file looks.",
                        "howToStart": "Sit with an engineer while they implement one of your designs and note every place the spec was ambiguous.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "qa-engineer",
        "title": "QA / Test Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Test case design",
                        "why": "Good testing is about systematically covering edge cases, not randomly clicking around an app.",
                        "howToStart": "Write a structured test plan (happy path, edge cases, error states) for one feature before testing it.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Test automation",
                        "why": "Manual regression testing doesn't scale as a product grows; automated suites are what keep releases fast and safe.",
                        "howToStart": "Automate the test cases for one feature you've been testing manually, using a framework like Playwright or Cypress.",
                    },
                    {
                        "name": "Bug reporting and triage",
                        "why": "A well-written bug report with clear repro steps gets fixed faster than a vague one, regardless of severity.",
                        "howToStart": "Rewrite your last five bug reports to each include exact repro steps, expected vs. actual behavior, and severity.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Performance and load testing",
                        "why": "Functional correctness and performance under load are separate concerns that need separate testing strategies.",
                        "howToStart": "Run a basic load test against one endpoint to find the point where response times start degrading.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "mobile-engineer",
        "title": "Mobile Engineer (iOS/Android)",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Platform UI fundamentals",
                        "why": "Mobile UI has different constraints (screen size, touch targets, platform conventions) than web.",
                        "howToStart": "Rebuild one common UI pattern (a settings screen, a list with pull-to-refresh) using your platform's native or cross-platform toolkit.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Offline-first data handling",
                        "why": "Mobile apps need to work with unreliable connectivity, which changes how state and sync are designed.",
                        "howToStart": "Add local caching and a sync strategy to one screen in an app so it still works with the network off.",
                    },
                    {
                        "name": "App store release process",
                        "why": "Shipping mobile software involves review processes and versioning constraints that web deploys don't have.",
                        "howToStart": "Take a personal app all the way through a store submission (even to a test track) to learn the real process end-to-end.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Battery and performance profiling",
                        "why": "Poor battery or memory behavior gets an app uninstalled even if every feature technically works.",
                        "howToStart": "Profile one screen of your app for memory and battery usage and fix the single largest offender.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "security-engineer",
        "title": "Security Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Common vulnerability classes",
                        "why": "Most real-world breaches trace back to a small, well-known set of vulnerability classes (injection, auth flaws, misconfiguration).",
                        "howToStart": "Work through a deliberately vulnerable practice app (an intentionally insecure web app used for training) and document each bug class you find.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Threat modeling",
                        "why": "Finding vulnerabilities after the fact is more expensive than designing systems that avoid whole classes of them upfront.",
                        "howToStart": "Threat-model one real feature you own: list its trust boundaries and what an attacker at each boundary could try.",
                    },
                    {
                        "name": "Secure code review",
                        "why": "Reviewing code for security issues is a distinct skill from reviewing it for correctness or style.",
                        "howToStart": "Review one pull request specifically for input validation, authz, and secret handling, ignoring everything else.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Incident response and forensics",
                        "why": "How quickly and correctly a team investigates a suspected breach determines the real damage done.",
                        "howToStart": "Write (or review) your team's incident response runbook and check it against a realistic breach scenario.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "engineering-manager",
        "title": "Engineering Manager",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "One-on-ones and feedback",
                        "why": "Regular, well-run one-on-ones are the primary mechanism for catching problems before they become resignations or missed deadlines.",
                        "howToStart": "Run a structured one-on-one with each report this week that is entirely about them, not status updates.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Technical planning and estimation",
                        "why": "Managers are accountable for realistic delivery timelines even when they're no longer writing most of the code.",
                        "howToStart": "Break down one upcoming project into tasks with your team and compare your estimate to theirs before committing a date.",
                    },
                    {
                        "name": "Performance management",
                        "why": "Clear, documented performance expectations are what make reviews and promotion decisions feel fair rather than arbitrary.",
                        "howToStart": "Write explicit, measurable expectations for one report's next review cycle and share them now, not at review time.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Org design and hiring",
                        "why": "As teams grow, how they're structured determines communication overhead and ownership clarity more than individual skill.",
                        "howToStart": "Map your team's current ownership boundaries and find the one area with unclear or overlapping responsibility.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "business-analyst",
        "title": "Business Analyst",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Requirements gathering",
                        "why": "Most project failures trace back to requirements that were assumed, not actually confirmed, with stakeholders.",
                        "howToStart": "Run a structured requirements interview for one real request and write it back to the stakeholder to confirm before any work starts.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Process mapping",
                        "why": "Visualizing a current process is what reveals where a proposed change will actually help or create new bottlenecks.",
                        "howToStart": "Map one real business process end-to-end (swimlane or flowchart) exactly as it happens today, not as it's supposed to happen.",
                    },
                    {
                        "name": "Data analysis for business decisions",
                        "why": "Recommendations backed by the underlying data are trusted and adopted far more often than ones backed by intuition alone.",
                        "howToStart": "Pull the actual numbers behind one recommendation you're about to make, before presenting it.",
                    },
                ],
            },
            {
                "stage": "Advanced",
                "skills": [
                    {
                        "name": "Stakeholder communication",
                        "why": "A technically correct analysis that stakeholders don't understand or trust does not change a decision.",
                        "howToStart": "Present your next finding as a one-slide summary with a clear recommendation before sharing the full analysis.",
                    },
                ],
            },
        ],
    },
]


def _mongo_options_from_environment() -> MongoOptions:
    return MongoOptions(
        url=os.environ.get("MONGODB_URL", "mongodb://localhost:27017"),
        database_name=os.environ.get("MONGODB_DATABASE", "Rezumi"),
        collection_name=os.environ.get("MONGODB_ROLE_ROADMAPS_COLLECTION", "role-roadmaps"),
    )


def seed_role_roadmaps(options: MongoOptions | None = None) -> int:
    """Upsert every curated roadmap document, keyed by roleSlug. Returns the count."""
    resolved = options or _mongo_options_from_environment()
    client: MongoClient[Any] = MongoClient(
        resolved.url,
        connectTimeoutMS=resolved.connect_timeout_ms,
        serverSelectionTimeoutMS=resolved.server_selection_timeout_ms,
    )
    try:
        collection = client[resolved.database_name][resolved.collection_name]
        collection.create_index("roleSlug", unique=True)
        now = datetime.now(UTC)
        for role in ROLE_ROADMAPS:
            document = {
                **role,
                "version": ROADMAP_VERSION,
                "sourceNote": "Self-authored starter content, not scraped from any third-party roadmap site.",
                "updatedAt": now,
            }
            collection.update_one(
                {"roleSlug": role["roleSlug"]},
                {"$set": document, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        return len(ROLE_ROADMAPS)
    finally:
        client.close()


def main() -> int:
    count = seed_role_roadmaps()
    print(f"Seeded {count} role roadmap documents (version {ROADMAP_VERSION}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
