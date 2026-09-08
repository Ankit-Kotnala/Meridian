"""Engineering, infrastructure, security, and adjacent builder roles."""

from __future__ import annotations

from typing import Any

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.builders import (
    role,
    skill,
    stage,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.shared import (
    ACCESSIBILITY,
    API_DESIGN,
    APPLICATION_PACKAGING,
    BEHAVIORAL_INTERVIEWS,
    CACHING,
    CICD,
    CLOUD_FUNDAMENTALS,
    CODE_REVIEW,
    COLLABORATION,
    COMPONENT_ARCHITECTURE,
    CONTAINERS,
    DEBUGGING,
    DISTRIBUTED_SYSTEMS,
    DOCUMENTATION,
    DSA,
    FORECASTING,
    HTML_CSS,
    INCIDENT_RESPONSE,
    INTERVIEW_EVIDENCE,
    JOB_DESCRIPTION_READING,
    JS_TS,
    KUBERNETES,
    LINUX,
    MESSAGE_QUEUES,
    NEGOTIATION,
    OBSERVABILITY,
    PERFORMANCE_WEB,
    PRIORITIZATION,
    PRODUCT_SPECS,
    RELATIONAL_DATABASES,
    RISK_TRACKING,
    SCALABILITY,
    SECURITY_BASICS,
    SQL,
    STAKEHOLDER_COMMUNICATION,
    SYSTEM_DESIGN,
    TAKE_HOME_ASSIGNMENTS,
    TESTING,
    VERSION_CONTROL,
)

ENGINEERING_ROLES: list[dict[str, Any]] = [
    role(
        "software-engineer",
        "Software Engineer",
        aliases=[
            "Software Developer",
            "Application Developer",
            "Backend Software Engineer",
            "SDE",
            "Software Development Engineer",
            "Programmer",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Programming language fluency",
                        "Teams hire people who can write, read, and debug one language well, not people who have sampled ten.",
                        "Pick one language used in jobs you want and build two small programs without a tutorial after the first hour.",
                    ),
                    DSA,
                    VERSION_CONTROL,
                    LINUX,
                    DEBUGGING,
                    skill(
                        "HTTP and how the web works",
                        "Most product bugs are request and response mistakes: status codes, headers, cookies, and caching.",
                        "Inspect one real request in browser tools or curl, reproduce it, and name every header that mattered.",
                    ),
                    SQL,
                    skill(
                        "Reading existing code",
                        "New jobs start with an unfamiliar codebase; the skill is tracing behavior, not rewriting it.",
                        "Pick an open-source file you did not write and map how a single request or command flows.",
                    ),
                    skill(
                        "IDE and editor fluency",
                        "Slow navigation and unused debugger features cost hours every week on a real team.",
                        "Learn ten shortcuts and one debugger workflow, then diagnose a bug without adding print statements.",
                    ),
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    TESTING,
                    CODE_REVIEW,
                    API_DESIGN,
                    RELATIONAL_DATABASES,
                    skill(
                        "Object-oriented and modular design",
                        "Unstructured code becomes unchangeable once more than one person owns it.",
                        "Refactor one tangled module into smaller units with explicit inputs, outputs, and tests.",
                    ),
                    skill(
                        "Error handling and reliability",
                        "Happy-path code fails in production; timeouts, retries, and user-visible errors are the real work.",
                        "List failure modes for one feature and add explicit handling for the two most likely ones.",
                    ),
                    CICD,
                    CONTAINERS,
                    CLOUD_FUNDAMENTALS,
                    OBSERVABILITY,
                    SECURITY_BASICS,
                    skill(
                        "Authentication and authorization",
                        "Most product security incidents start as confused identity: who is the user, and what may they do.",
                        "Implement login plus one permission check and test a user who must be denied.",
                    ),
                    CACHING,
                    COLLABORATION,
                    skill(
                        "Agile delivery and tickets",
                        "Engineering output is planned in a tracker; unclear tickets create rework.",
                        "Turn one vague request into a ticket with problem, acceptance checks, and a test note.",
                    ),
                    skill(
                        "Code quality and refactoring",
                        "Shipping only new features leaves a codebase that nobody can safely change.",
                        "Make one behavior-preserving refactor with tests before and after.",
                    ),
                ],
            ),
            stage(
                "Systems and production",
                [
                    SYSTEM_DESIGN,
                    DISTRIBUTED_SYSTEMS,
                    MESSAGE_QUEUES,
                    SCALABILITY,
                    KUBERNETES,
                    INCIDENT_RESPONSE,
                    skill(
                        "Database query performance",
                        "Slow pages are often missing indexes, N+1 queries, or unbounded scans.",
                        "Explain one slow query with its plan, then add an index or rewrite and measure the change.",
                    ),
                    skill(
                        "Networking for application engineers",
                        "DNS, TLS, load balancers, and timeouts show up in every production outage eventually.",
                        "Trace one user request from DNS to your process and write where it can fail.",
                    ),
                    skill(
                        "Infrastructure as code",
                        "Click-ops environments cannot be reviewed or reproduced.",
                        "Encode one environment as code and apply it in a throwaway account.",
                    ),
                    skill(
                        "Event-driven design",
                        "Asynchronous events decouple writers from readers, but they create ordering and replay bugs.",
                        "Replace one synchronous side effect with an event and a consumer, then test duplicate delivery.",
                    ),
                    skill(
                        "API contracts across services",
                        "Breaking a JSON field is a production incident for someone else.",
                        "Add a typed contract for one endpoint and a consumer test that fails on a breaking change.",
                    ),
                    skill(
                        "Cost-aware engineering",
                        "Cloud bills grow from chatty APIs, chatty queries, and forgotten resources.",
                        "Attribute last month's cost of one service to the top three drivers.",
                    ),
                    skill(
                        "Privacy and data handling",
                        "Logs, analytics, and backups often store personal data without an owner noticing.",
                        "Inventory personal data in one service and write retention, access, and deletion for each field.",
                    ),
                ],
            ),
            stage(
                "Professional practice",
                [
                    skill(
                        "Technical design documents",
                        "Senior work is decided in writing before it is built so others can challenge the design.",
                        "Write a short design doc for one change: context, options, decision, and risks.",
                    ),
                    skill(
                        "Mentoring and knowledge sharing",
                        "Teams scale when people teach, not when one person remains the only expert.",
                        "Give one pairing session or written walkthrough and collect two questions you could not answer.",
                    ),
                    skill(
                        "Estimating and scoping",
                        "Missed dates usually come from unstated work: tests, migration, rollout, and support.",
                        "Estimate one project as must / should / later slices, including rollout and rollback.",
                    ),
                    skill(
                        "Working with product and design",
                        "Engineers who only wait for tickets miss cheaper solutions a short conversation would surface.",
                        "Join one product discussion before implementation with one constraint and one simpler alternative.",
                    ),
                    skill(
                        "Open-source and internal libraries",
                        "Reinventing logging or HTTP clients creates bugs a maintained library already solved.",
                        "Replace one homemade utility with a maintained library and document the behavior you still own.",
                    ),
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                    TAKE_HOME_ASSIGNMENTS,
                    skill(
                        "Live coding interviews",
                        "Interview coding is a communication exercise under time, not a hidden IQ test.",
                        "Practice one medium problem out loud: restate, example, brute force, then improve.",
                    ),
                    skill(
                        "System design interviews",
                        "Design interviews reward clarifying requirements and failure modes more than drawing every box.",
                        "Time-box a 30-minute design of a familiar product: requirements, API, data, and one bottleneck.",
                    ),
                ],
            ),
        ],
    ),
    role(
        "frontend-engineer",
        "Frontend Engineer",
        aliases=["Front End Engineer", "UI Engineer", "Web Engineer", "Client-Side Engineer"],
        stages=[
            stage(
                "Foundations",
                [HTML_CSS, JS_TS, VERSION_CONTROL, DEBUGGING, DOCUMENTATION],
            ),
            stage(
                "Core skills",
                [
                    COMPONENT_ARCHITECTURE,
                    ACCESSIBILITY,
                    TESTING,
                    CODE_REVIEW,
                    skill(
                        "State management",
                        "Most frontend bugs are inconsistent state across URL, server, and UI.",
                        "Document the source of truth for one screen and remove one duplicate store.",
                    ),
                    skill(
                        "Frontend data fetching",
                        "Waterfalls, cache misses, and missing error states are product bugs.",
                        "Implement loading, empty, error, and success for one list view, including retry.",
                    ),
                    skill(
                        "Design-to-engineering handoff",
                        "Spacing, empty states, and wrap behavior matter more than matching one mock exactly.",
                        "Implement one design with all interactive states, not only the happy mock.",
                    ),
                    skill(
                        "Forms and validation",
                        "Forms are where users give identity and money; silent failures destroy trust.",
                        "Build one form with inline errors, keyboard submit, and a disabled state that explains why.",
                    ),
                    CICD,
                    SECURITY_BASICS,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    PERFORMANCE_WEB,
                    skill(
                        "Frontend security",
                        "XSS, CSRF, and tokens in local storage are frontend-owned incidents.",
                        "Review one app for untrusted HTML and token storage, then fix the worst issue.",
                    ),
                    skill(
                        "Internationalization",
                        "Copy length, RTL, and locale dates break layouts tested only in English.",
                        "Run one screen with long dummy copy and a non-English date, then fix overflow.",
                    ),
                    skill(
                        "Design systems consumption",
                        "Most product UI is composition of an existing system, not one-off CSS.",
                        "Replace custom styles on one page with design-system components and document gaps.",
                    ),
                    OBSERVABILITY,
                    INCIDENT_RESPONSE,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    TAKE_HOME_ASSIGNMENTS,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "backend-engineer",
        "Backend Engineer",
        aliases=["Server Engineer", "API Engineer", "Backend Developer", "Services Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Server-side language fluency",
                        "Backend interviews and on-call assume production code in the team's language.",
                        "Implement one small HTTP service with validation, tests, and structured errors.",
                    ),
                    RELATIONAL_DATABASES,
                    SQL,
                    API_DESIGN,
                    VERSION_CONTROL,
                    LINUX,
                    TESTING,
                    DEBUGGING,
                ],
            ),
            stage(
                "Core skills",
                [
                    CACHING,
                    MESSAGE_QUEUES,
                    CICD,
                    CONTAINERS,
                    OBSERVABILITY,
                    SECURITY_BASICS,
                    skill(
                        "Transactions and consistency",
                        "Lost updates come from ignoring transactions, uniqueness, and retries.",
                        "Write one inventory-style flow with a uniqueness constraint and an idempotency key.",
                    ),
                    skill(
                        "Pagination, filtering, and idempotency",
                        "List endpoints that cannot page or retry safely fail the first mobile client.",
                        "Add cursor pagination and idempotent POST semantics to one API.",
                    ),
                    CODE_REVIEW,
                    CLOUD_FUNDAMENTALS,
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    SCALABILITY,
                    DISTRIBUTED_SYSTEMS,
                    SYSTEM_DESIGN,
                    KUBERNETES,
                    INCIDENT_RESPONSE,
                    skill(
                        "Schema migration",
                        "Expand/contract migrations keep APIs available; big-bang ALTER TABLE is an outage plan.",
                        "Practice one backward-compatible column add, dual-write, then remove the old field.",
                    ),
                    skill(
                        "Capacity and load testing",
                        "Guessing QPS is how teams discover the limit in production.",
                        "Load-test one endpoint, record p95 and the first bottleneck.",
                    ),
                    skill(
                        "Secrets and configuration",
                        "Hard-coded credentials remain a leading cause of breaches and outages.",
                        "Move secrets out of source for one service and document rotation.",
                    ),
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    TAKE_HOME_ASSIGNMENTS,
                    BEHAVIORAL_INTERVIEWS,
                    SYSTEM_DESIGN,
                ],
            ),
        ],
    ),
    role(
        "full-stack-engineer",
        "Full-Stack Engineer",
        aliases=["Full Stack Developer", "Fullstack Engineer", "Full-Stack Developer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "End-to-end feature ownership",
                        "Full-stack roles own a feature from data to UI, not a pile of unrelated frameworks.",
                        "Build one small feature completely: schema, API, and UI.",
                    ),
                    HTML_CSS,
                    JS_TS,
                    RELATIONAL_DATABASES,
                    VERSION_CONTROL,
                    TESTING,
                    DEBUGGING,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "API contracts across the stack",
                        "Full-stack engineers feel contract drift first when frontend and backend assumptions diverge.",
                        "Add a typed contract between frontend and backend on one project.",
                    ),
                    skill(
                        "Deployment basics",
                        "A feature that only runs locally is not delivered.",
                        "Deploy one full-stack app with HTTPS, logs, and a documented rollback.",
                    ),
                    API_DESIGN,
                    COMPONENT_ARCHITECTURE,
                    ACCESSIBILITY,
                    CICD,
                    SECURITY_BASICS,
                    OBSERVABILITY,
                    COLLABORATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    SYSTEM_DESIGN,
                    PERFORMANCE_WEB,
                    SCALABILITY,
                    INCIDENT_RESPONSE,
                    skill(
                        "Cross-layer debugging",
                        "Full-stack incidents bounce between UI, API, and data until someone traces the real boundary.",
                        "Diagnose one bug that spans UI and API by capturing the request, status, and database write.",
                    ),
                    CONTAINERS,
                    CLOUD_FUNDAMENTALS,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    TAKE_HOME_ASSIGNMENTS,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "mobile-engineer",
        "Mobile Engineer",
        aliases=["iOS Engineer", "Android Engineer", "Mobile Developer", "Mobile App Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Platform UI fundamentals",
                        "iOS and Android have platform layout, navigation, and lifecycle rules that web habits do not cover.",
                        "Build one small screen using only platform UI components and handle rotation or configuration change.",
                    ),
                    VERSION_CONTROL,
                    TESTING,
                    DEBUGGING,
                    skill(
                        "Mobile app architecture",
                        "Unstructured view controllers and activities become untestable within a few features.",
                        "Split one screen into UI, state, and data layers with a test around the state layer.",
                    ),
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Offline-first data",
                        "Mobile networks drop; apps that only work on perfect Wi-Fi fail real users.",
                        "Add local persistence and a retry queue for one write the user must not lose.",
                    ),
                    skill(
                        "Push notifications and deep links",
                        "Retention and support flows depend on notifications that open the right screen.",
                        "Implement one notification that deep-links to a specific screen with invalid-payload handling.",
                    ),
                    skill(
                        "App store release process",
                        "Shipping mobile software includes signing, store review, and staged rollout, not only a merge.",
                        "Walk one build through signing, a store listing draft, and a rollback plan.",
                    ),
                    skill(
                        "Battery, storage, and performance",
                        "Background work and unbounded caches get apps killed or uninstalled.",
                        "Profile one screen for dropped frames and one background job for wakeups.",
                    ),
                    ACCESSIBILITY,
                    SECURITY_BASICS,
                    CICD,
                    CODE_REVIEW,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Mobile security and local data",
                        "Tokens and personal data on device are a breach if storage and backup are ignored.",
                        "Audit one app's local storage and move secrets into the platform keystore or equivalent.",
                    ),
                    OBSERVABILITY,
                    INCIDENT_RESPONSE,
                    skill(
                        "Cross-platform tradeoffs",
                        "Shared code saves time until platform UX or performance forces a native path.",
                        "Write a one-page decision for one feature: native, shared, or hybrid, with the constraint that decided it.",
                    ),
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    TAKE_HOME_ASSIGNMENTS,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "devops-sre-engineer",
        "DevOps / Site Reliability Engineer",
        aliases=[
            "Site Reliability Engineer",
            "SRE",
            "DevOps Engineer",
            "Platform Engineer",
            "Infrastructure Engineer",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    LINUX,
                    skill(
                        "Networking basics",
                        "DNS, routing, TLS, and firewalls are how production traffic actually moves.",
                        "Trace one public hostname to an IP and port, and write where TLS terminates.",
                    ),
                    VERSION_CONTROL,
                    CONTAINERS,
                    CLOUD_FUNDAMENTALS,
                    DEBUGGING,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    CICD,
                    KUBERNETES,
                    skill(
                        "Infrastructure as code",
                        "If it is not in code, it is not reviewable and will drift.",
                        "Encode one environment in Terraform or equivalent and apply it twice to prove it is idempotent.",
                    ),
                    OBSERVABILITY,
                    INCIDENT_RESPONSE,
                    skill(
                        "Monitoring and alerting",
                        "Pages that fire on noise train people to ignore real outages.",
                        "Write one alert with a user-visible symptom, a runbook link, and a quiet period.",
                    ),
                    SECURITY_BASICS,
                    skill(
                        "Backup and restore",
                        "A backup that has never been restored is a hope, not a control.",
                        "Restore one dataset into a throwaway environment and time how long it takes.",
                    ),
                    COLLABORATION,
                    TESTING,
                ],
            ),
            stage(
                "Advanced",
                [
                    SCALABILITY,
                    DISTRIBUTED_SYSTEMS,
                    skill(
                        "SLIs, SLOs, and error budgets",
                        "Reliability work needs a numeric user promise, not a feeling that it has been a bad week.",
                        "Define one SLI and SLO for a service you know and list what you would stop shipping if the budget burned.",
                    ),
                    skill(
                        "Cost optimization",
                        "Idle compute and orphaned disks are reliability and finance problems at once.",
                        "Find the three largest cost items in one account and propose one safe reduction.",
                    ),
                    skill(
                        "Progressive delivery",
                        "All-at-once deploys turn every release into a possible site-wide outage.",
                        "Add a canary or blue/green path for one service with an automatic rollback signal.",
                    ),
                    SYSTEM_DESIGN,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                    TAKE_HOME_ASSIGNMENTS,
                ],
            ),
        ],
    ),
    role(
        "security-engineer",
        "Security Engineer",
        aliases=[
            "Application Security Engineer",
            "Product Security Engineer",
            "Cybersecurity Engineer",
            "AppSec Engineer",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Security fundamentals",
                        "Confidentiality, integrity, availability, and least privilege are how you judge any control.",
                        "Threat-model one app on a whiteboard: assets, actors, and the two most likely abuses.",
                    ),
                    LINUX,
                    skill(
                        "TCP/IP and network security",
                        "Many incidents are exposed services, weak TLS, or flat networks, not exotic malware.",
                        "Document TLS termination and unnecessary open ports for one service you operate in a lab.",
                    ),
                    VERSION_CONTROL,
                    SECURITY_BASICS,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Vulnerability assessment",
                        "Finding issues is useless without severity, reproduction, and a fix path the owning team can ship.",
                        "Triage one finding with impact, exploitability, and a concrete patch or compensating control.",
                    ),
                    skill(
                        "Threat modeling",
                        "Controls without a threat model become checkbox theater.",
                        "Run a short threat model on one feature before it ships and log the two risks you accepted.",
                    ),
                    skill(
                        "Secure code review",
                        "Most exploitable bugs are ordinary code review misses: authz, injection, and secret handling.",
                        "Review one pull request with an authz and injection checklist, and file issues for what you found.",
                    ),
                    skill(
                        "Identity and access management",
                        "Broken access control remains a top web risk because permission checks are inconsistent.",
                        "Map roles to permissions for one app and add a test that a lesser role cannot hit an admin action.",
                    ),
                    skill(
                        "Cloud security",
                        "Public buckets, over-broad IAM, and missing logs are still common cloud incidents.",
                        "Review one cloud account for public storage and unused admin keys, then close the worst gap.",
                    ),
                    INCIDENT_RESPONSE,
                    TESTING,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Detection and forensics basics",
                        "Response requires evidence: timestamps, identity, and what changed, not guesswork.",
                        "Write an investigation timeline for one simulated incident using logs you actually have.",
                    ),
                    skill(
                        "Application security testing",
                        "SAST, DAST, and dependency scanning only help if findings are triaged into the backlog.",
                        "Run one scanner on a repo you own and close or explicitly accept the top five issues.",
                    ),
                    skill(
                        "Security program reporting",
                        "Leadership funds what they can see: residual risk, not a pile of unprioritized CVEs.",
                        "Write a one-page risk summary for one system with owner, due date, and user impact.",
                    ),
                    SYSTEM_DESIGN,
                    OBSERVABILITY,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                    TAKE_HOME_ASSIGNMENTS,
                ],
            ),
        ],
    ),
    role(
        "qa-engineer",
        "QA Engineer",
        aliases=["Quality Engineer", "SDET", "Test Engineer", "QA Analyst", "Software Tester"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Test case design",
                        "Unsystematic testing finds the same happy path repeatedly and misses the defect users hit.",
                        "Write cases for one feature covering valid, invalid, boundary, and permission-denied inputs.",
                    ),
                    skill(
                        "Bug reporting",
                        "A bug without reproduction, expected result, and environment will be bounced.",
                        "File one report with steps, actual vs expected, and a screenshot or log excerpt.",
                    ),
                    VERSION_CONTROL,
                    TESTING,
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Test automation",
                        "Manual regression does not scale; automation has to be stable enough that people trust failures.",
                        "Automate the five highest-value checks for one flow and delete one flaky assertion.",
                    ),
                    skill(
                        "API testing",
                        "UI tests are slow; contract and API tests catch most regressions earlier.",
                        "Write automated checks for one API's success, validation, and authorization failures.",
                    ),
                    skill(
                        "Exploratory testing",
                        "Scripts miss surprising combinations; skilled exploration still finds production bugs.",
                        "Spend one focused hour on a charter and log issues you would not have scripted.",
                    ),
                    CICD,
                    ACCESSIBILITY,
                    SECURITY_BASICS,
                    skill(
                        "Test data and environments",
                        "Flaky tests are often environment drift and shared data, not bad assertions.",
                        "Make one suite create and clean its own data so it can run twice in a row.",
                    ),
                    CODE_REVIEW,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Performance and load testing",
                        "Correctness at one user is not correctness at peak traffic.",
                        "Run a load test against one endpoint and record the first bottleneck.",
                    ),
                    skill(
                        "Quality strategy",
                        "Senior QA work is choosing what not to automate and where risk actually lives.",
                        "Write a test strategy for one release: risks, layers, and what you will not cover.",
                    ),
                    OBSERVABILITY,
                    INCIDENT_RESPONSE,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    TAKE_HOME_ASSIGNMENTS,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "engineering-manager",
        "Engineering Manager",
        aliases=["Software Engineering Manager", "Development Manager", "EM"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "One-on-ones",
                        "People problems fester when the only conversation is stand-up status.",
                        "Run a 1:1 agenda that covers work, growth, and blockers, and write down commitments.",
                    ),
                    COLLABORATION,
                    DOCUMENTATION,
                    skill(
                        "Delivery planning",
                        "A team without a visible plan will be pulled in five directions by the loudest request.",
                        "Publish a two-week plan with owners, dependencies, and what will wait.",
                    ),
                    INTERVIEW_EVIDENCE,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Technical planning",
                        "Managers who cannot engage with design reviews cannot protect quality or dates.",
                        "Review one design doc and ask about rollback, data, and the riskiest assumption.",
                    ),
                    skill(
                        "Performance management",
                        "Unspoken expectations become surprise ratings; written goals can be coached.",
                        "Write one person's current goals with evidence you would actually look at.",
                    ),
                    skill(
                        "Hiring and interviewing",
                        "A weak hiring bar is a multi-year tax on the team.",
                        "Define a scorecard for one role and run a structured interview against it.",
                    ),
                    skill(
                        "Stakeholder communication",
                        "Executives need risk and options, not a tour of Jira.",
                        "Write a weekly update with what shipped, what slipped, and the decision you need.",
                    ),
                    INCIDENT_RESPONSE,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Org design",
                        "Team shape decides who is overloaded and which systems have no owner.",
                        "Draw your team's systems and people, then mark the single-threaded ownership gaps.",
                    ),
                    skill(
                        "Coaching without taking the keyboard",
                        "Managers who always jump in to code become the bottleneck they were hired to remove.",
                        "Coach one engineer through a design instead of writing it, and record what they decided.",
                    ),
                    SYSTEM_DESIGN,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "solutions-architect",
        "Solutions Architect",
        aliases=["Solution Architect", "Technical Architect", "Enterprise Architect"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Requirements-to-architecture",
                        "Architecture that ignores constraints is a slide, not a design.",
                        "Turn one customer or internal requirement into a diagram with constraints and non-goals.",
                    ),
                    SYSTEM_DESIGN,
                    CLOUD_FUNDAMENTALS,
                    API_DESIGN,
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Integration patterns",
                        "Most enterprise work is connecting systems without creating a mesh of unowned failure modes.",
                        "Choose sync vs async for one integration and write the retry and idempotency rules.",
                    ),
                    skill(
                        "Non-functional requirements",
                        "Latency, RPO/RTO, and compliance change the design more than the happy-path feature list.",
                        "Write NFRs for one system with numbers, not adjectives.",
                    ),
                    SECURITY_BASICS,
                    RELATIONAL_DATABASES,
                    OBSERVABILITY,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Architecture decision records",
                        "Decisions evaporate unless the context and rejected alternatives are written down.",
                        "Write one ADR for a real choice including the option you did not take.",
                    ),
                    DISTRIBUTED_SYSTEMS,
                    SCALABILITY,
                    INCIDENT_RESPONSE,
                    skill(
                        "Cost-aware architecture",
                        "Architecture that ignores unit cost will be rewritten by finance.",
                        "Estimate monthly cost for one design at 10x traffic and name the first expensive assumption.",
                    ),
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                    SYSTEM_DESIGN,
                ],
            ),
        ],
    ),
    role(
        "cloud-engineer",
        "Cloud Engineer",
        aliases=["Cloud Infrastructure Engineer", "AWS Engineer", "Azure Engineer", "GCP Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    CLOUD_FUNDAMENTALS,
                    LINUX,
                    VERSION_CONTROL,
                    skill(
                        "Cloud networking",
                        "Most cloud outages are routing, DNS, or security-group mistakes, not missing instance types.",
                        "Draw one VPC-or-equivalent network with public/private paths and a documented egress route.",
                    ),
                    CONTAINERS,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Infrastructure as code",
                        "Cloud click-ops cannot be reviewed, reused, or recovered after an accidental delete.",
                        "Encode one environment as code and apply it twice to prove it is idempotent.",
                    ),
                    CICD,
                    KUBERNETES,
                    OBSERVABILITY,
                    SECURITY_BASICS,
                    skill(
                        "Identity in the cloud",
                        "Over-broad roles and long-lived keys are the usual cloud breach path.",
                        "Replace one static key with a short-lived role and document who can assume it.",
                    ),
                    INCIDENT_RESPONSE,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Multi-account and landing zones",
                        "A single shared account mixes prod, dev, and billing until an incident makes that obvious.",
                        "Sketch an account or project layout with blast-radius boundaries for one company.",
                    ),
                    skill(
                        "Cost optimization",
                        "Idle disks and forgotten load balancers are engineering work, not only finance work.",
                        "Find the three largest cost items in one account and propose one safe reduction.",
                    ),
                    SCALABILITY,
                    SYSTEM_DESIGN,
                    DISTRIBUTED_SYSTEMS,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                    TAKE_HOME_ASSIGNMENTS,
                ],
            ),
        ],
    ),
    role(
        "database-administrator",
        "Database Administrator",
        aliases=["DBA", "Database Engineer", "PostgreSQL DBA", "MySQL DBA"],
        stages=[
            stage(
                "Foundations",
                [
                    RELATIONAL_DATABASES,
                    SQL,
                    LINUX,
                    VERSION_CONTROL,
                    DOCUMENTATION,
                    skill(
                        "Backup and restore",
                        "A backup that has never been restored is not a backup.",
                        "Restore one database into a throwaway environment and time the recovery.",
                    ),
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Query performance",
                        "Most 'the database is slow' tickets are missing indexes, bad plans, or lock contention.",
                        "Capture one slow query plan, change it, and record the before/after timing.",
                    ),
                    skill(
                        "Replication and failover",
                        "High availability is a failover test, not a replica that nobody has promoted.",
                        "Document one failover path and run it in a lab, including application connection changes.",
                    ),
                    skill(
                        "Access control and auditing",
                        "Shared superuser credentials turn every incident into an untraceable event.",
                        "Replace one shared login with role-based access and enable audit for privileged changes.",
                    ),
                    OBSERVABILITY,
                    SECURITY_BASICS,
                    INCIDENT_RESPONSE,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Capacity planning",
                        "Disk, connections, and autovacuum/equivalent limits fail suddenly if they are not tracked.",
                        "Write a capacity note for one database: growth rate, headroom, and the first limit you will hit.",
                    ),
                    SCALABILITY,
                    SYSTEM_DESIGN,
                    skill(
                        "Schema change safety",
                        "Locking migrations take production down even when the SQL looks simple.",
                        "Practice one expand/contract change with a rollback that does not require restoring from backup.",
                    ),
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "network-engineer",
        "Network Engineer",
        aliases=["Network Administrator", "Network Operations Engineer", "NOC Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "TCP/IP fundamentals",
                        "Packet paths, not vendor GUIs, are how you explain an outage.",
                        "Capture one conversation with ping/traceroute/packet tools and write the hop list.",
                    ),
                    LINUX,
                    DOCUMENTATION,
                    skill(
                        "Switching and routing",
                        "Loops, asymmetric routing, and missing routes still cause most LAN/WAN tickets.",
                        "Draw one network you can access and mark L2 vs L3 boundaries.",
                    ),
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Firewall and segmentation",
                        "Flat networks turn one compromised laptop into an organization-wide incident.",
                        "Write an allow-list for one application path and deny everything else in a lab.",
                    ),
                    skill(
                        "DNS and certificates",
                        "A large share of 'the internet is down' is DNS TTL, split horizon, or expired TLS.",
                        "Trace one hostname from resolver to certificate expiry and calendar the renewal.",
                    ),
                    OBSERVABILITY,
                    INCIDENT_RESPONSE,
                    SECURITY_BASICS,
                    skill(
                        "Wireless and remote access",
                        "Hybrid work means VPN, zero-trust, and Wi-Fi capacity are production systems.",
                        "Document one remote-access path and the identity that gates it.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Network automation",
                        "Clicking the same ACL change on twenty boxes is how drift and outages happen.",
                        "Automate one repetitive network change with a diff you can review before apply.",
                    ),
                    SCALABILITY,
                    SYSTEM_DESIGN,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "it-support-specialist",
        "IT Support Specialist",
        aliases=[
            "Help Desk Specialist",
            "Desktop Support",
            "IT Support Engineer",
            "Service Desk Analyst",
            "Technical Support Specialist",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Ticket hygiene",
                        "A ticket without reproduction, device, and user impact cannot be escalated usefully.",
                        "Rewrite five tickets with steps, expected result, and what you already tried.",
                    ),
                    skill(
                        "Systematic troubleshooting",
                        "Randomly reinstalling software hides the actual cause and trains users to skip you next time.",
                        "Use a change-one-variable method on one issue and log the disproven hypotheses.",
                    ),
                    LINUX,
                    skill(
                        "Endpoint and identity basics",
                        "Most access issues are group membership, MFA, or device compliance, not 'the server'.",
                        "Trace one access failure from user identity to device policy to the app.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Customer communication under pressure",
                        "Users in an outage need status and next step, not jargon.",
                        "Write a three-sentence user update for one incident: impact, workaround, next update time.",
                    ),
                    SECURITY_BASICS,
                    skill(
                        "Asset and patch hygiene",
                        "Untracked laptops and unpatched browsers are the common ransomware entry.",
                        "Inventory one set of devices and close the oldest critical patch gap you are allowed to close.",
                    ),
                    INCIDENT_RESPONSE,
                    OBSERVABILITY,
                    skill(
                        "Knowledge base writing",
                        "If only you can fix a repeating issue, you will never leave the queue.",
                        "Publish one article with symptoms, cause, and the exact fix, then have a teammate follow it.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Automation for support",
                        "Resetting the same permission by hand is a process failure.",
                        "Automate one repetitive support task with an audit log.",
                    ),
                    PRIORITIZATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "sales-engineer",
        "Sales Engineer",
        aliases=[
            "Solutions Engineer",
            "Solutions Consultant",
            "Pre-Sales Engineer",
            "Technical Account Engineer",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Technical discovery",
                        "A demo that ignores the buyer's actual constraint wastes the cycle.",
                        "Write a discovery checklist covering stack, security review, and success metric for one deal.",
                    ),
                    PRODUCT_SPECS,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Product demonstration",
                        "A demo that follows the script instead of the buyer's workflow loses technical buyers.",
                        "Run one demo against a real customer story, including the failure case they asked about.",
                    ),
                    skill(
                        "Technical objection handling",
                        "Security, SSO, and data residency questions are the deal, not a side quest.",
                        "Write honest answers for five common objections, including what you cannot do.",
                    ),
                    skill(
                        "Proof-of-concept discipline",
                        "Unbounded POCs consume engineering and never end.",
                        "Write success criteria, time-box, and exit for one POC before any environment is built.",
                    ),
                    SYSTEM_DESIGN,
                    SECURITY_BASICS,
                    API_DESIGN,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Solution architecture for deals",
                        "Enterprise deals need a design the customer's architects can live with after signature.",
                        "Produce one architecture one-pager with trust boundaries and operational owners.",
                    ),
                    NEGOTIATION,
                    FORECASTING,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "game-developer",
        "Game Developer",
        aliases=["Gameplay Engineer", "Unity Developer", "Unreal Developer", "Game Programmer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Game loop and real-time programming",
                        "Games fail when update order, timing, and frame budget are treated as afterthoughts.",
                        "Build a tiny loop with input, update, and render, and measure frame time.",
                    ),
                    DSA,
                    VERSION_CONTROL,
                    DEBUGGING,
                    TESTING,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Gameplay systems",
                        "Most shipped games are data-driven systems, not one-off scripts in a scene.",
                        "Implement one mechanic as data plus code so a designer can tune it without a rebuild.",
                    ),
                    skill(
                        "Physics and collision debugging",
                        "Player-facing bugs are often collision layers and interpolation, not 'the engine'.",
                        "Reproduce one physics glitch, name the layer/order cause, and write a regression check.",
                    ),
                    skill(
                        "Asset pipelines",
                        "Build breaks from unversioned art more often than from gameplay code.",
                        "Document import settings and a failed-build path for one asset type.",
                    ),
                    PERFORMANCE_WEB,
                    CICD,
                    COLLABORATION,
                    CODE_REVIEW,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Multiplayer and determinism",
                        "Desync and cheating appear as soon as two clients share state carelessly.",
                        "Sketch one lockstep or server-authoritative model and list what the client is not allowed to decide.",
                    ),
                    SYSTEM_DESIGN,
                    OBSERVABILITY,
                    INCIDENT_RESPONSE,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    TAKE_HOME_ASSIGNMENTS,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
    role(
        "embedded-engineer",
        "Embedded Engineer",
        aliases=["Firmware Engineer", "Embedded Software Engineer", "IoT Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "C or C++ for constrained devices",
                        "Embedded work still lives close to memory, interrupts, and hardware registers.",
                        "Write one bare-metal or RTOS blink-and-uart program with a watchdog in mind.",
                    ),
                    LINUX,
                    VERSION_CONTROL,
                    DEBUGGING,
                    DOCUMENTATION,
                    TESTING,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Hardware bring-up",
                        "Software that assumes the schematic is the board will debug the wrong layer for days.",
                        "Write a bring-up checklist for one board: power, clocks, and the first peripheral you prove.",
                    ),
                    skill(
                        "RTOS and concurrency on device",
                        "Priority inversion and missed deadlines are production bugs, not academic topics.",
                        "Instrument one task for worst-case latency and document the budget.",
                    ),
                    SECURITY_BASICS,
                    CICD,
                    OBSERVABILITY,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "OTA and field updates",
                        "A bricked fleet is an incident that cannot be SSH'd.",
                        "Design one update path with dual banks or equivalent rollback.",
                    ),
                    INCIDENT_RESPONSE,
                    SYSTEM_DESIGN,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                    TAKE_HOME_ASSIGNMENTS,
                ],
            ),
        ],
    ),
    role(
        "technical-program-manager",
        "Technical Program Manager",
        aliases=["TPM", "Technical Project Manager", "Program Manager"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Scope and timeline",
                        "A program without a written scope will absorb every adjacent request.",
                        "Write a one-page scope with in/out, milestones, and the first dependency you cannot slip.",
                    ),
                    RISK_TRACKING,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Cross-functional coordination",
                        "TPMs succeed by making hidden work and owners visible, not by writing the code.",
                        "Publish a RACI for one launch and resolve the first owner conflict in writing.",
                    ),
                    skill(
                        "Status reporting",
                        "Status that hides red items until the week of launch is how programs fail publicly.",
                        "Write a status with green/yellow/red, the date it changed, and the decision needed.",
                    ),
                    SYSTEM_DESIGN,
                    PRIORITIZATION,
                    INCIDENT_RESPONSE,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Program risk and dependency graphs",
                        "The critical path is rarely the task people talk about in stand-up.",
                        "Draw dependencies for one program and name the task whose slip moves the launch.",
                    ),
                    BEHAVIORAL_INTERVIEWS,
                    FORECASTING,
                ],
            ),
            stage(
                "Hiring market",
                [
                    JOB_DESCRIPTION_READING,
                    APPLICATION_PACKAGING,
                    INTERVIEW_EVIDENCE,
                    BEHAVIORAL_INTERVIEWS,
                ],
            ),
        ],
    ),
]
