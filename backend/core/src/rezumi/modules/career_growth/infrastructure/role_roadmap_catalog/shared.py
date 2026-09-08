"""Reusable self-authored skill entries shared across many role roadmaps."""

from __future__ import annotations

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.builders import skill

VERSION_CONTROL = skill(
    "Version control",
    "Git is how teams share, review, and recover code without overwriting each other.",
    "Practice a full branch, commit, pull-request, and review cycle on a personal project.",
)
TESTING = skill(
    "Testing",
    "Automated tests let a team change code without re-checking every path by hand.",
    "Add unit tests to one existing project until each core function has a passing case and a failing-case test.",
)
SYSTEM_DESIGN = skill(
    "System design",
    "Beyond entry level, engineers must reason about services, data, and failure modes together.",
    "Sketch the architecture of a product you use daily, then compare it with a public write-up.",
)
DSA = skill(
    "Data structures and algorithms",
    "Interviews and day-to-day debugging assume fluency with core structures and time/space tradeoffs.",
    "Pick one structure a week and re-implement it from scratch before using a library version.",
)
SQL = skill(
    "SQL",
    "Most product data still lives in relational stores, and weak SQL hides as slow features.",
    "Write ten queries against a public dataset covering filters, joins, grouping, and window functions.",
)
RELATIONAL_DATABASES = skill(
    "Relational databases",
    "Backend systems are shaped by how data is modeled, constrained, and queried.",
    "Design a normalized schema for a small real domain and write the queries a real app would need.",
)
API_DESIGN = skill(
    "API design",
    "A large part of engineering is defining contracts other systems and teammates depend on.",
    "Write the contract for one feature first, then implement against that contract.",
)
CICD = skill(
    "CI/CD pipelines",
    "A pipeline that tests and deploys on every change is how teams ship without heroics.",
    "Build a pipeline that runs tests and publishes an artifact on merge for one personal project.",
)
LINUX = skill(
    "Linux and command line",
    "Production debugging still happens on Linux hosts, logs, and processes, not only in an IDE.",
    "Administer one Linux VM or container: users, processes, logs, networking, and a systemd-or-equivalent service.",
)
DEBUGGING = skill(
    "Debugging",
    "Most engineering time is spent diagnosing unexpected behavior, not writing the first version.",
    "Take one real bug and write the hypothesis, evidence, and disproof steps before changing code.",
)
CODE_REVIEW = skill(
    "Code review",
    "Review is how teams share standards and catch defects before they reach users.",
    "Review one pull request as if you owned the production incident it might cause, and write specific comments.",
)
OBSERVABILITY = skill(
    "Observability",
    "You cannot operate what you cannot see: logs, metrics, and traces are how production is understood.",
    "Add structured logs, one golden metric, and a trace around one request path in a personal service.",
)
SECURITY_BASICS = skill(
    "Secure coding basics",
    "Injection, auth mistakes, and secret leaks are still the most common ways software is compromised.",
    "Run an OWASP-informed review of one project and fix the highest-severity finding you can reproduce.",
)
CLOUD_FUNDAMENTALS = skill(
    "Cloud fundamentals",
    "Most teams run on a public cloud, and identity, networking, and cost are part of the job.",
    "Deploy one small service to a cloud account and document IAM, networking, and the monthly cost drivers.",
)
CONTAINERS = skill(
    "Containers",
    "Containers are the common packaging unit between laptops, CI, and production.",
    "Dockerize one app, add a health check, and run it locally with a compose file.",
)
KUBERNETES = skill(
    "Kubernetes",
    "Many production platforms schedule work on Kubernetes, so deploy, probe, and rollback skills transfer widely.",
    "Deploy one small app to a local cluster with probes, resource limits, and a recorded rollback.",
)
CACHING = skill(
    "Caching",
    "Caching is a common way to meet latency and load targets without rewriting the whole system.",
    "Add a cache in front of one expensive query and measure hit rate, staleness, and invalidation.",
)
MESSAGE_QUEUES = skill(
    "Message queues",
    "Queues decouple slow or unreliable work from the request path once traffic is real.",
    "Move one slow operation behind a queue and a worker in a personal project.",
)
DISTRIBUTED_SYSTEMS = skill(
    "Distributed systems",
    "Production systems run across machines, which adds partitions, retries, and partial failure.",
    "Read one real postmortem and name the failure mode that actually caused the outage.",
)
SCALABILITY = skill(
    "Scalability",
    "Designing for more than one instance changes assumptions about state, locking, and coordination.",
    "List every place a service you built assumes only one instance is running.",
)
INCIDENT_RESPONSE = skill(
    "Incident response",
    "When production breaks, the skill is to mitigate first, communicate, then find the cause.",
    "Run a tabletop for one past outage: detection, mitigation, comms, and a follow-up action.",
)
DOCUMENTATION = skill(
    "Technical documentation",
    "Code that cannot be operated or handed off is unfinished, even if it works on your machine.",
    "Write a one-page runbook for one service covering start, stop, health, and the last incident.",
)
COLLABORATION = skill(
    "Written collaboration",
    "Most engineering work is coordination: tickets, design notes, and status that other people can act on.",
    "Rewrite one vague ticket into a problem, constraint, proposal, and test plan.",
)
STAKEHOLDER_COMMUNICATION = skill(
    "Stakeholder communication",
    "Work dies when the people who need a decision cannot see tradeoffs in plain language.",
    "Write a one-page update for a non-engineer that states the decision, options, and what you need from them.",
)
PRIORITIZATION = skill(
    "Prioritization",
    "Teams fail when everything is urgent; ranking work against an explicit goal is the actual job.",
    "Rank your current work against one outcome metric and drop or delay the lowest item this week.",
)
EXPERIMENT_DESIGN = skill(
    "Experiment design",
    "Shipping a change without a comparison leaves you guessing whether it helped.",
    "Design one A/B or before/after test with a metric, sample, and stop rule before looking at results.",
)
SQL_STORYTELLING = skill(
    "Data storytelling",
    "A correct query is unused if the audience cannot see the decision it supports.",
    "Turn one analysis into a three-sentence brief: what changed, why it matters, and what to do next.",
)
ACCESSIBILITY = skill(
    "Accessibility",
    "Accessible interfaces are a legal requirement in many contexts and simply usable by more people.",
    "Navigate one page you built using only a keyboard and a screen reader, then fix what breaks.",
)
HTML_CSS = skill(
    "HTML and CSS",
    "Every UI framework compiles down to HTML and CSS; layout bugs are cheapest to fix at that layer.",
    "Rebuild one webpage layout with semantic HTML and CSS Grid or Flexbox, no framework.",
)
JS_TS = skill(
    "JavaScript / TypeScript fundamentals",
    "Frameworks change; closures, async, and the type checker stay underneath day-to-day debugging.",
    "Write a small app with fetch and the DOM APIs only, then add types where a bug hid.",
)
COMPONENT_ARCHITECTURE = skill(
    "Component architecture",
    "Production frontend work is mostly organizing state and props, not inventing new widgets.",
    "Split one oversized component into smaller ones with a single responsibility each.",
)
PERFORMANCE_WEB = skill(
    "Performance optimization",
    "Render cost and bundle size affect real retention, especially on slower devices.",
    "Run a Lighthouse or Web Vitals audit on one page and fix the single largest issue.",
)
PYTHON = skill(
    "Python",
    "Python is the common language for automation, data work, and a large share of backend services.",
    "Build one small command-line tool that reads a file, validates input, and writes a tested output.",
)
STATISTICS = skill(
    "Applied statistics",
    "Without variance, sample size, and confounding, dashboards become stories you cannot defend.",
    "Take one metric you care about and write the denominator, window, and what would invalidate it.",
)
MACHINE_LEARNING = skill(
    "Machine learning and deep learning fundamentals",
    "Training, overfitting, embeddings, and evaluation are how you diagnose model behavior instead of guessing.",
    "Train and compare two simple models on one public dataset, documenting metric, baseline, and failures.",
)
PRODUCT_SPECS = skill(
    "Product specs",
    "A spec that names the user, constraint, and success signal prevents building the wrong thing politely.",
    "Write a one-page spec for a feature you want: problem, users, non-goals, and how you will know it worked.",
)
USER_RESEARCH = skill(
    "User research methods",
    "Opinions are cheap; watching a real person try the product changes what you build next.",
    "Run five short interviews or usability sessions on one flow and write the pattern, not the quotes dump.",
)
DISCOVERY = skill(
    "Discovery and qualification",
    "Time spent on deals or projects that were never going to complete is the largest efficiency leak.",
    "Write a qualification checklist and apply it honestly to your current pipeline or backlog.",
)
NEGOTIATION = skill(
    "Negotiation and closing",
    "Deals and offers stall when you decide concessions under pressure instead of in advance.",
    "Before your next negotiation, write what you can concede, what you cannot, and your walk-away.",
)
FORECASTING = skill(
    "Forecast accuracy",
    "Hiring, spend, and board conversations use the forecast; an inflated one causes real downstream damage.",
    "Compare last period's forecast to actuals and name the specific items you were overconfident about.",
)
PROCESS_MAPPING = skill(
    "Process mapping",
    "You cannot improve a workflow you have not made visible, including the unofficial workarounds.",
    "Map one end-to-end process with owners, systems, and wait states, then circle the longest delay.",
)
RISK_TRACKING = skill(
    "Risk tracking",
    "Surprises are usually risks that were visible weeks earlier and never written down.",
    "Start a risk log for one project with likelihood, impact, owner, and the next mitigation date.",
)
FINANCIAL_MODELING = skill(
    "Financial modeling",
    "Decisions about hiring, pricing, and investment need a model someone else can audit.",
    "Build a three-statement or unit-economics model for one scenario and list every assumption.",
)
EMPLOYMENT_LAW = skill(
    "Employment law basics",
    "People decisions that ignore local employment rules create legal and human harm.",
    "Read your jurisdiction's core employee handbook topics and write what you are not allowed to improvise.",
)
SOURCING = skill(
    "Sourcing",
    "A hiring pipeline that only waits for inbound applicants will miss the people you actually need.",
    "Source ten qualified profiles for one role and write why each one might or might not be a fit.",
)
INVENTORY = skill(
    "Inventory and demand",
    "Too much stock ties up cash; too little stock loses customers. Both are forecast and lead-time problems.",
    "For one SKU or resource, write demand, lead time, and the cost of being wrong in each direction.",
)
INTERVIEW_EVIDENCE = skill(
    "Evidence-backed interviewing",
    "Interviews that invent achievements fail later; answers must map to work you can actually show.",
    "Pick three likely interview stories and attach each to a Career Record artifact you already have, or write the missing evidence question.",
)
JOB_DESCRIPTION_READING = skill(
    "Job description decoding",
    "Postings mix must-haves, nice-to-haves, and leftover template text; treating them equally wastes applications.",
    "Highlight one posting into required evidence, optional evidence, and claims you will not make.",
)
APPLICATION_PACKAGING = skill(
    "Application packaging",
    "A tailored resume, answers, and tracker beat spraying the same file at fifty listings.",
    "Build one application pack for a real posting: mapped evidence, unanswered gaps, and a follow-up date.",
)
BEHAVIORAL_INTERVIEWS = skill(
    "Behavioral interviews",
    "Most loops ask for a situation, action, and result; unspecific stories sound invented.",
    "Write five STAR stories from real work, each with a named team, constraint, and observable result.",
)
TAKE_HOME_ASSIGNMENTS = skill(
    "Take-home assignments",
    "Take-homes test judgment and communication as much as code, and overbuilding is a common fail.",
    "Time-box one practice assignment, write the tradeoffs you skipped, and include a README a reviewer can grade.",
)

HIRING_MARKET_SKILLS = [
    JOB_DESCRIPTION_READING,
    APPLICATION_PACKAGING,
    INTERVIEW_EVIDENCE,
    BEHAVIORAL_INTERVIEWS,
    TAKE_HOME_ASSIGNMENTS,
]
