"""Seed the curated role-roadmap library (Phase 13).

This content is self-authored and versioned — never scraped from roadmap.sh
or any other third-party roadmap site (their licenses do not permit
reproducing their content elsewhere; see ADR 0019 §5 and the plan that
introduced this feature). It intentionally covers a starting set of common
tech/product roles, not every possible job title — the document shape below
makes adding more roles a matter of appending an entry, not a schema change.

Run with:

    uv run --project backend python -m rezumi.development.seed_role_roadmaps

or, against the running local stack:

    make seed-role-roadmaps
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient

from rezumi.foundation.config.mongodb import MongoOptions

ROADMAP_VERSION = "role-roadmaps/2026-08-23.2"

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
    {
        "roleSlug": "data-analyst",
        "title": "Data Analyst",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "SQL",
                        "why": "Almost every analysis starts with pulling and shaping data yourself, and SQL is the shared language for that across nearly every company.",
                        "howToStart": "Write one query a day against a public dataset until joins, group-by, and window functions all feel routine, not intimidating.",
                    },
                    {
                        "name": "Data visualization",
                        "why": "A correct analysis that's presented in a confusing chart gets ignored; the visualization is often the actual deliverable.",
                        "howToStart": "Rebuild one chart from a report you admire from scratch, matching its choice of chart type and labeling exactly.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Statistics for business decisions",
                        "why": "Knowing whether a difference in the data is real or noise is what separates a defensible recommendation from a guess.",
                        "howToStart": "Run a basic significance test on one A/B-style comparison you have real data for, and write down what it would take to change your conclusion.",
                    },
                    {
                        "name": "Data storytelling",
                        "why": "Stakeholders act on the narrative and recommendation, not the raw numbers — analysts who can't frame both get ignored.",
                        "howToStart": "Turn your next finding into a three-sentence story: what happened, why it matters, what to do about it.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "technical-writer",
        "title": "Technical Writer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Audience analysis",
                        "why": "The same feature needs a different document for a new user, an integrator, and an on-call engineer — writing for the wrong one wastes everyone's time.",
                        "howToStart": "Before writing your next doc, write one sentence describing exactly who will read it and what they need to do afterward.",
                    },
                    {
                        "name": "Information architecture",
                        "why": "Readers scan, not read start-to-end; if they can't find the one section they need, the rest of the document doesn't matter.",
                        "howToStart": "Outline one existing long document as a heading tree only, then check whether someone could find an answer in under 30 seconds.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Working with subject-matter experts",
                        "why": "Technical writers rarely have the deepest knowledge in the room — getting accurate detail out of busy experts efficiently is the core skill.",
                        "howToStart": "Prepare five specific questions before your next SME interview instead of asking them to 'explain the feature.'",
                    },
                    {
                        "name": "Docs-as-code tooling",
                        "why": "Most modern documentation lives in the same version control and review workflow as the product code it describes.",
                        "howToStart": "Move one piece of writing into a Markdown file in a git repo and open a real pull request for it, review comments included.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "ux-researcher",
        "title": "UX Researcher",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Research method selection",
                        "why": "Using the wrong method (a survey when you needed interviews, usability testing when you needed analytics) produces confident, wrong answers.",
                        "howToStart": "Before your next study, write down the specific decision it needs to inform, then pick the method that decision actually requires.",
                    },
                    {
                        "name": "Interviewing without leading",
                        "why": "A leading question gets you the answer you expected, not the truth about how someone actually behaves.",
                        "howToStart": "Record one practice interview and count how many of your questions could be answered with a simple yes or no — rewrite those as open questions.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Synthesis and affinity mapping",
                        "why": "Raw interview notes are not insights; turning scattered observations into a small number of clear themes is the actual research output.",
                        "howToStart": "Take the raw notes from your last five user conversations and group every quote into no more than five themes before writing conclusions.",
                    },
                    {
                        "name": "Research advocacy",
                        "why": "Findings that never reach the people building the product don't change anything, no matter how rigorous the study was.",
                        "howToStart": "Turn your next research readout into a one-page summary with the top three findings and a specific recommended action for each.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "project-manager",
        "title": "Project Manager",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Scope and timeline planning",
                        "why": "Most project trouble starts with a scope or deadline nobody actually validated against the real amount of work.",
                        "howToStart": "Break your next project into tasks small enough that each one is a single day of work or less, then total the estimate before committing to a date.",
                    },
                    {
                        "name": "Risk tracking",
                        "why": "The risks that sink a project are almost always ones someone saw coming but never wrote down or escalated.",
                        "howToStart": "Keep a running risk log for your current project and review it in every status meeting, not just when something goes wrong.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Cross-functional coordination",
                        "why": "A project manager's real leverage is keeping dependent teams synchronized, not doing the work of any one team.",
                        "howToStart": "Map every cross-team dependency in your current project on one page before the next milestone, and confirm each owner agrees with it.",
                    },
                    {
                        "name": "Status reporting",
                        "why": "Stakeholders make better decisions when they get an honest, concise status update instead of a vague 'on track.'",
                        "howToStart": "Rewrite your next status update to lead with the single biggest risk to the deadline, not the list of completed tasks.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "scrum-master",
        "title": "Scrum Master",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Agile ceremony facilitation",
                        "why": "A standup or retro that runs long or produces no decisions trains the team to stop taking it seriously.",
                        "howToStart": "Time-box your next retro to 30 minutes and end it with at least one concrete action item assigned to a named person.",
                    },
                    {
                        "name": "Impediment removal",
                        "why": "The scrum master's actual job is clearing blockers the team can't clear themselves — not just tracking the board.",
                        "howToStart": "Pick one blocker your team has mentioned twice without resolution and personally own getting it removed this week.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Team metrics and flow",
                        "why": "Velocity and cycle time only help if you use them to spot real problems, not as a score to optimize for its own sake.",
                        "howToStart": "Track your team's cycle time for one sprint and identify the single stage (review, testing, deploy) where work sits longest.",
                    },
                    {
                        "name": "Coaching without authority",
                        "why": "A scrum master has no direct authority over the team, so influence has to come from trust and clear reasoning, not a title.",
                        "howToStart": "The next time you disagree with a team decision, ask one clarifying question before offering your own opinion.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "solutions-architect",
        "title": "Solutions Architect",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Requirements-to-architecture translation",
                        "why": "A solutions architect's job is turning a business need into a concrete technical shape a team can actually build.",
                        "howToStart": "Take one vague business requirement you've seen and write two different technical approaches with the tradeoffs of each.",
                    },
                    {
                        "name": "Integration patterns",
                        "why": "Most real solutions architecture work is connecting existing systems, not building something from scratch.",
                        "howToStart": "Diagram how data flows between two systems you use today (batch, event-driven, or synchronous API) and label where it could fail.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Non-functional requirements",
                        "why": "Scalability, security, and cost constraints decide whether a design survives contact with production, not just whether it works in a demo.",
                        "howToStart": "For your next design, write down the expected load and failure tolerance before choosing any technology.",
                    },
                    {
                        "name": "Stakeholder-facing technical communication",
                        "why": "Architects present to both engineers and executives, and a design nobody outside the room understands won't get approved or built correctly.",
                        "howToStart": "Explain your current design to someone outside engineering using no acronyms, and note which parts they couldn't follow.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "cloud-engineer",
        "title": "Cloud Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Core cloud services",
                        "why": "Compute, storage, and networking primitives are what every higher-level cloud service is built from, and debugging requires knowing them.",
                        "howToStart": "Provision one small workload by hand in a cloud console (not a template) so you see every configuration choice explicitly.",
                    },
                    {
                        "name": "Infrastructure as code",
                        "why": "Manually configured infrastructure can't be reliably reproduced, reviewed, or rolled back — code can.",
                        "howToStart": "Recreate the workload you just built by hand using a Terraform or CloudFormation template instead, and destroy/recreate it to prove it's repeatable.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Cost optimization",
                        "why": "Cloud bills grow silently, and identifying what's actually driving cost is a distinct skill from provisioning resources.",
                        "howToStart": "Pull last month's cost breakdown for one project and identify the single largest line item you didn't expect.",
                    },
                    {
                        "name": "Cloud security fundamentals",
                        "why": "Misconfigured permissions and open resources are the most common real-world cloud incidents, not exotic attacks.",
                        "howToStart": "Audit one resource's access policy and remove every permission that isn't demonstrably needed.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "database-administrator",
        "title": "Database Administrator",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Schema design and normalization",
                        "why": "A poorly normalized schema causes data integrity problems and slow queries that are expensive to fix after the fact.",
                        "howToStart": "Take one existing table with repeated or redundant columns and redesign it into a properly normalized schema.",
                    },
                    {
                        "name": "Backup and recovery",
                        "why": "A backup strategy that's never been tested is not actually a backup strategy — it's an assumption.",
                        "howToStart": "Restore a real backup to a scratch environment and time how long it takes, before you need to do it under pressure.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Query performance tuning",
                        "why": "Most database performance problems come from a handful of slow queries or missing indexes, not the hardware.",
                        "howToStart": "Find the slowest query in one system you maintain, read its execution plan, and add the index that removes the biggest cost.",
                    },
                    {
                        "name": "Replication and high availability",
                        "why": "Production databases need to survive a node failure without losing data or going fully offline.",
                        "howToStart": "Set up basic replication between two database instances in a test environment and simulate a primary failure.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "network-engineer",
        "title": "Network Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "TCP/IP and routing fundamentals",
                        "why": "Every network problem eventually traces back to how packets are routed, and that requires a solid model of the underlying protocols.",
                        "howToStart": "Trace the full path of one request from your machine to a public server using traceroute and explain each hop.",
                    },
                    {
                        "name": "Network troubleshooting",
                        "why": "Most network issues are diagnosed by isolating where in the path a failure occurs, not by guessing at the cause.",
                        "howToStart": "The next time something is 'slow on the network,' use packet capture tools to find exactly where the delay is before touching any configuration.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Firewall and segmentation design",
                        "why": "A flat network where every host can reach every other host turns one compromised machine into a full breach.",
                        "howToStart": "Diagram the network segments in one environment you manage and identify one place a firewall rule is missing or too permissive.",
                    },
                    {
                        "name": "Network monitoring",
                        "why": "Problems caught by monitoring get fixed before users notice; problems found by user complaints already cost trust.",
                        "howToStart": "Set up one alert for a network metric (latency, packet loss, or bandwidth) that would have caught your last real incident earlier.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "it-support-specialist",
        "title": "IT Support Specialist",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Systematic troubleshooting",
                        "why": "Guessing at fixes wastes time and often masks the real problem; a repeatable process finds root cause faster.",
                        "howToStart": "For your next ticket, write down your hypothesis before trying a fix, then confirm whether the fix actually addressed that hypothesis.",
                    },
                    {
                        "name": "Ticket documentation",
                        "why": "A resolved ticket with no notes helps nobody the next time the same issue happens to someone else.",
                        "howToStart": "Add a one-line root cause and fix summary to every ticket you close this week, even the quick ones.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Endpoint and identity management",
                        "why": "Most support work at scale is managing devices and access consistently, not one-off troubleshooting.",
                        "howToStart": "Document the full provisioning checklist for a new hire's laptop and accounts, then find one step that's still manual and could be automated.",
                    },
                    {
                        "name": "Customer communication under pressure",
                        "why": "A frustrated user needs to feel heard before they'll patiently wait through a real fix.",
                        "howToStart": "Practice acknowledging the impact of an issue in your first response before explaining any technical detail.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "sales-engineer",
        "title": "Sales Engineer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Technical discovery",
                        "why": "A demo built before understanding the prospect's actual technical environment and constraints usually misses the point that closes the deal.",
                        "howToStart": "Before your next demo, write down the prospect's specific technical stack and the one problem they need solved, and tailor the demo to just that.",
                    },
                    {
                        "name": "Product demonstration",
                        "why": "A sales engineer's core deliverable is showing, concretely, how the product solves the prospect's problem — not a generic feature tour.",
                        "howToStart": "Record yourself giving your standard demo, then cut every part that isn't directly tied to a customer pain point.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Handling technical objections",
                        "why": "Deals are frequently lost or won on how credibly technical concerns (security, integration, scale) are addressed.",
                        "howToStart": "List the five technical objections you hear most often and write a specific, evidence-backed answer for each.",
                    },
                    {
                        "name": "Proof-of-concept design",
                        "why": "A well-scoped proof of concept proves the exact thing the customer needs proven, and nothing more — a poorly scoped one drags on for months.",
                        "howToStart": "For your next POC, write the specific success criteria with the customer before any work starts, not after.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "customer-success-manager",
        "title": "Customer Success Manager",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Onboarding design",
                        "why": "A customer's long-term retention is often decided in their first 30 days, not by anything that happens later.",
                        "howToStart": "Map your current onboarding flow step by step and find the single point where customers most often stall or drop off.",
                    },
                    {
                        "name": "Account health monitoring",
                        "why": "Churn is easier to prevent when it's spotted from usage and engagement signals weeks before the customer says anything.",
                        "howToStart": "Pick three usage signals that predict churn for your product and check them for your accounts weekly, not just at renewal time.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Renewal and expansion conversations",
                        "why": "Renewals and upsells go smoother when the value delivered has already been made explicit, not argued for at the last minute.",
                        "howToStart": "Before your next renewal conversation, prepare a one-page summary of the concrete value the customer has already gotten.",
                    },
                    {
                        "name": "Cross-functional escalation",
                        "why": "A CSM's credibility depends on getting real product or support issues resolved, not just relaying customer complaints.",
                        "howToStart": "The next time a customer reports a real issue, personally track it to resolution and report back, instead of just forwarding the ticket.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "marketing-manager",
        "title": "Marketing Manager",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Positioning and messaging",
                        "why": "Every campaign, page, and ad depends on a clear answer to who this is for and why it matters — without that, tactics don't compound.",
                        "howToStart": "Write a one-paragraph positioning statement for your product and test it against three real customers to see if it matches how they describe it.",
                    },
                    {
                        "name": "Campaign planning",
                        "why": "A campaign without a specific goal and audience produces activity, not results.",
                        "howToStart": "For your next campaign, write the target audience, single goal, and success metric before choosing any channel or creative.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Marketing analytics",
                        "why": "Knowing which channels and campaigns actually drove results is what separates real budget decisions from guesses.",
                        "howToStart": "Pull the full funnel numbers (impressions to conversion) for your last campaign and identify the stage with the biggest drop-off.",
                    },
                    {
                        "name": "Cross-functional campaign execution",
                        "why": "Marketing managers coordinate design, content, and sales — a great idea that no one executes on time doesn't ship.",
                        "howToStart": "Build a simple shared timeline for your next campaign with named owners for every deliverable, not just a list of tasks.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "content-strategist",
        "title": "Content Strategist",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Audience and content mapping",
                        "why": "Content that isn't mapped to a specific audience and stage in their journey tends to be generic and gets ignored.",
                        "howToStart": "List your three most important audience segments and one specific question or need each has that content could answer.",
                    },
                    {
                        "name": "Editorial planning",
                        "why": "Consistent, planned content compounds; reactive, one-off content rarely builds an audience.",
                        "howToStart": "Build a four-week content calendar tied to specific goals, and track what gets published against the plan.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Content performance measurement",
                        "why": "Without measurement, content strategy is just opinion about what should work.",
                        "howToStart": "Pick one published piece and trace its actual engagement and conversion data, then decide whether to do more of that format.",
                    },
                    {
                        "name": "Content governance and consistency",
                        "why": "As content scales across writers and channels, inconsistent voice and quality erode trust in the brand.",
                        "howToStart": "Write a one-page style and tone guide from examples of your best existing content, and use it to review the next piece someone else writes.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "growth-marketer",
        "title": "Growth Marketer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Funnel analysis",
                        "why": "Growth work starts with knowing exactly where in the funnel users drop off, not guessing at which lever to pull.",
                        "howToStart": "Map your product's full funnel from first visit to activation and quantify the drop-off at each step.",
                    },
                    {
                        "name": "Experiment design",
                        "why": "Growth ideas that aren't tested with a real experiment just add noise, good or bad, that nobody can attribute correctly.",
                        "howToStart": "Design one A/B test with a clear hypothesis and success metric before changing anything live.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Channel-specific acquisition tactics",
                        "why": "Paid, organic, referral, and lifecycle channels each have different mechanics, and generic tactics rarely transfer between them.",
                        "howToStart": "Pick one acquisition channel your product doesn't fully use yet and run one small, measurable test in it.",
                    },
                    {
                        "name": "Retention and lifecycle marketing",
                        "why": "Acquiring users who don't come back is often more expensive than keeping the ones you already have engaged.",
                        "howToStart": "Identify the point where users typically stop returning and design one lifecycle message aimed specifically at that moment.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "seo-specialist",
        "title": "SEO Specialist",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Keyword research",
                        "why": "Ranking for the wrong keywords, even at position one, brings traffic that doesn't convert.",
                        "howToStart": "Pick one page you want to rank better and find three keyword variants with real search volume it currently doesn't target.",
                    },
                    {
                        "name": "On-page and technical SEO",
                        "why": "Content that search engines can't crawl, parse, or trust to load quickly won't rank no matter how good it is.",
                        "howToStart": "Run a technical audit on one page (title tags, headings, load time, mobile rendering) and fix the single biggest issue you find.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Link building and authority",
                        "why": "Search engines weigh how many other trusted sites link to a page, not just its own content quality.",
                        "howToStart": "Identify one legitimate, relevant site that could plausibly link to your content and reach out with a specific, useful reason to.",
                    },
                    {
                        "name": "SEO analytics and reporting",
                        "why": "Rankings alone don't prove business value; traffic and conversion from organic search do.",
                        "howToStart": "Build one report connecting organic traffic to an actual business outcome (signups, revenue) for your top three pages.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "financial-analyst",
        "title": "Financial Analyst",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Financial modeling",
                        "why": "Most financial decisions run through a model, and a model with a wrong assumption baked in silently produces a wrong decision.",
                        "howToStart": "Build a simple three-statement model for a company you know well and stress-test it by changing one assumption at a time.",
                    },
                    {
                        "name": "Variance analysis",
                        "why": "Understanding exactly why actuals differed from the forecast is what makes the next forecast more accurate.",
                        "howToStart": "Take last month's actuals vs. budget for one line item and trace the specific driver behind the variance.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Business partnering",
                        "why": "Analysis that never reaches decision-makers in a form they can use doesn't influence the decision.",
                        "howToStart": "Turn your next analysis into a one-page recommendation memo instead of a raw spreadsheet, and share it with the actual decision-maker.",
                    },
                    {
                        "name": "Valuation methods",
                        "why": "Comparing investment or business decisions requires a consistent way to value future cash flows against each other.",
                        "howToStart": "Value one real or hypothetical investment using discounted cash flow and check your result against a market comparable.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "accountant",
        "title": "Accountant",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Double-entry bookkeeping",
                        "why": "Every other accounting skill assumes fluency with how debits and credits keep the books balanced.",
                        "howToStart": "Record a full month of transactions for a small real or practice business by hand before relying on software to do it for you.",
                    },
                    {
                        "name": "Month-end close process",
                        "why": "A late or error-prone close delays every downstream report and decision that depends on accurate numbers.",
                        "howToStart": "Write out every step of your close process with a target completion day, and track which steps consistently run late.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Reconciliations",
                        "why": "Discrepancies between internal records and external statements are often the first sign of an error or fraud.",
                        "howToStart": "Fully reconcile one account you own down to zero difference, documenting every adjusting entry you make and why.",
                    },
                    {
                        "name": "Financial reporting standards",
                        "why": "Reports that don't follow the applicable standard (GAAP, IFRS) can't be trusted or audited by external parties.",
                        "howToStart": "Pick one financial statement you prepare and check each line item against the specific standard that governs it.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "hr-generalist",
        "title": "HR Generalist",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Employment law basics",
                        "why": "Even routine HR decisions (leave, discipline, termination) carry legal exposure if the basics aren't understood.",
                        "howToStart": "Read your jurisdiction's core requirements for one process you handle often (leave, termination) and check your current practice against it.",
                    },
                    {
                        "name": "Employee relations",
                        "why": "Most day-to-day HR work is handling conflicts and concerns fairly and consistently, not policy writing.",
                        "howToStart": "Document your standard process for handling one type of employee concern so it's applied the same way every time, regardless of who raises it.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Performance management systems",
                        "why": "A performance process that feels arbitrary erodes trust faster than having no formal process at all.",
                        "howToStart": "Review your current performance review template and remove any criteria that can't be tied to specific, observable behavior.",
                    },
                    {
                        "name": "HR data and reporting",
                        "why": "Decisions about retention, hiring, and compensation are stronger when backed by actual workforce data, not anecdotes.",
                        "howToStart": "Pull your team's turnover rate for the last year and identify the one department or tenure band driving most of it.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "technical-recruiter",
        "title": "Technical Recruiter",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Technical role and skill literacy",
                        "why": "A recruiter who can't tell a strong resume from a keyword-stuffed one wastes hiring managers' time on the wrong candidates.",
                        "howToStart": "Sit with a hiring manager through one technical screen and write down the specific signals they used to say yes or no.",
                    },
                    {
                        "name": "Sourcing strategy",
                        "why": "For competitive roles, the best candidates usually aren't the ones who applied — they have to be found and approached.",
                        "howToStart": "Build a search string that surfaces candidates matching your hardest-to-fill role, and reach out to five with a specific, non-generic message.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Candidate experience management",
                        "why": "A disorganized or slow process loses strong candidates to competitors regardless of how good the role is.",
                        "howToStart": "Time your current process from first contact to offer, and fix the single longest gap in that timeline.",
                    },
                    {
                        "name": "Offer negotiation",
                        "why": "Losing a finalist candidate over an avoidable negotiation misstep is one of the most expensive recruiting mistakes.",
                        "howToStart": "Before your next offer call, write down the candidate's likely priorities (comp, title, remote) and your actual flexibility on each.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "operations-manager",
        "title": "Operations Manager",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Process documentation",
                        "why": "An undocumented process only works as long as the one person who knows it stays, and it can't be improved systematically.",
                        "howToStart": "Document one core recurring process end-to-end, then have someone unfamiliar with it try to follow your instructions exactly.",
                    },
                    {
                        "name": "KPI tracking",
                        "why": "Operations decisions without a small set of tracked metrics tend to react to whatever problem is loudest that week.",
                        "howToStart": "Pick three metrics that best represent operational health for your team and start tracking them weekly, even manually at first.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Vendor and resource management",
                        "why": "Operations managers are often accountable for costs and reliability they don't directly control, which runs through vendor relationships.",
                        "howToStart": "Review one active vendor contract against actual usage and identify a specific cost or service gap.",
                    },
                    {
                        "name": "Process improvement",
                        "why": "A process that works today usually breaks as volume grows; improvement is a continuous responsibility, not a one-time project.",
                        "howToStart": "Find the slowest step in one process you own and redesign just that step, then measure whether it actually got faster.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "supply-chain-analyst",
        "title": "Supply Chain Analyst",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Demand forecasting",
                        "why": "Over- or under-forecasting demand drives most of the excess inventory or stockout problems a supply chain deals with.",
                        "howToStart": "Build a simple forecast for one product line using historical data and compare it against what actually happened last period.",
                    },
                    {
                        "name": "Inventory management",
                        "why": "Balancing carrying cost against stockout risk is the central tradeoff of supply chain work, not just tracking quantities.",
                        "howToStart": "Calculate the reorder point for one SKU based on its actual lead time and demand variability, not a rule of thumb.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Supplier performance analysis",
                        "why": "A cheaper supplier that delivers late or inconsistently often costs more overall than a slightly pricier reliable one.",
                        "howToStart": "Score your top three suppliers on on-time delivery and defect rate using real data from the last quarter, not reputation.",
                    },
                    {
                        "name": "Logistics cost optimization",
                        "why": "Transportation and warehousing costs are often the largest controllable line item in the supply chain.",
                        "howToStart": "Break down the shipping cost for one product's full journey and identify the single most expensive leg.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "graphic-designer",
        "title": "Graphic Designer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Typography and layout",
                        "why": "Weak typography and layout undermine even strong concepts — most viewers notice bad spacing before they notice a clever idea.",
                        "howToStart": "Redesign one piece of existing marketing material using only better typography and spacing, no new imagery.",
                    },
                    {
                        "name": "Brand system application",
                        "why": "Most professional design work happens inside an existing brand system, not as a blank-canvas creative exercise.",
                        "howToStart": "Take one brand's guidelines and design three different assets (social post, flyer, banner) that all clearly belong to the same brand.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Design critique and iteration",
                        "why": "First drafts are rarely the final answer; the ability to take specific feedback and iterate is what separates professional output.",
                        "howToStart": "Share one design for critique before you think it's finished, and revise it based on the two most specific pieces of feedback.",
                    },
                    {
                        "name": "Production-ready file preparation",
                        "why": "A design that looks great on screen but isn't prepared correctly for print or web causes costly delays and rework.",
                        "howToStart": "Take one finished design through the full production checklist (color mode, resolution, export formats) for its actual output channel.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "ux-writer",
        "title": "UX Writer",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Microcopy and interface writing",
                        "why": "Button labels, error messages, and empty states are often the only 'content' most users ever read, and bad ones cause real confusion.",
                        "howToStart": "Rewrite the five worst error messages or button labels in a product you use, focusing on clarity over cleverness.",
                    },
                    {
                        "name": "Voice and tone consistency",
                        "why": "Inconsistent voice across a product makes it feel unpolished even when the visual design is strong.",
                        "howToStart": "Audit ten UI strings across one product flow and flag every one that doesn't match the intended voice and tone.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Content testing",
                        "why": "Assuming copy is clear because the writer understands it is a common mistake; real users often read it differently.",
                        "howToStart": "Test two versions of one confusing piece of UI copy with a handful of real users and see which one they understand faster.",
                    },
                    {
                        "name": "Collaborating with design and engineering",
                        "why": "UX writing decided in isolation often gets overridden or ignored once implementation constraints show up.",
                        "howToStart": "Join one design review before copy is finalized and flag any place where a technical or layout constraint changes what you can write.",
                    },
                ],
            },
        ],
    },
    {
        "roleSlug": "sales-account-executive",
        "title": "Account Executive",
        "stages": [
            {
                "stage": "Foundations",
                "skills": [
                    {
                        "name": "Discovery and qualification",
                        "why": "Time spent on deals that were never going to close is the single biggest efficiency loss for most sales reps.",
                        "howToStart": "Write a specific qualification checklist (budget, need, timeline, decision-maker) and apply it honestly to your current pipeline.",
                    },
                    {
                        "name": "Pipeline management",
                        "why": "A pipeline that isn't accurately staged leads to unreliable forecasts and surprises at quarter end.",
                        "howToStart": "Review every deal in your pipeline this week and move any deal to the stage it actually belongs in, even if that means downgrading it.",
                    },
                ],
            },
            {
                "stage": "Core skills",
                "skills": [
                    {
                        "name": "Negotiation and closing",
                        "why": "Deals stall or shrink most often when a rep doesn't have a clear plan for handling price pushback or a competing option.",
                        "howToStart": "Before your next negotiation, decide in advance what you can concede and what you can't, so you're not deciding under pressure.",
                    },
                    {
                        "name": "Forecast accuracy",
                        "why": "Sales leadership makes hiring, spending, and board-level decisions based on the forecast, so an inflated one causes real downstream damage.",
                        "howToStart": "Compare your forecast from last quarter to what actually closed, and identify which specific deals you were overconfident about.",
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
