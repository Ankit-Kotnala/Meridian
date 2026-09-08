"""Business analysis, delivery, finance, and people roles."""

from __future__ import annotations

from typing import Any

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.builders import (
    role,
    skill,
    stage,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.shared import (
    COLLABORATION,
    DOCUMENTATION,
    EMPLOYMENT_LAW,
    FINANCIAL_MODELING,
    FORECASTING,
    HIRING_MARKET_SKILLS,
    NEGOTIATION,
    PRIORITIZATION,
    PROCESS_MAPPING,
    PRODUCT_SPECS,
    RISK_TRACKING,
    SOURCING,
    SQL,
    SQL_STORYTELLING,
    STAKEHOLDER_COMMUNICATION,
)

BUSINESS_ROLES: list[dict[str, Any]] = [
    role(
        "business-analyst",
        "Business Analyst",
        aliases=["BA", "IT Business Analyst", "Systems Analyst", "Business Systems Analyst"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Requirements gathering",
                        "Unstated requirements become defects and change requests.",
                        "Interview two stakeholders for one process and write must / should / later with owners.",
                    ),
                    PROCESS_MAPPING,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    SQL,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Process documentation",
                        "A process that lives in one person's head cannot be improved or automated.",
                        "Document one process with inputs, systems, decisions, and exceptions.",
                    ),
                    skill(
                        "Acceptance criteria",
                        "Stories without testable criteria will be argued at the demo.",
                        "Write Given/When/Then or equivalent for one change including the failure path.",
                    ),
                    PRODUCT_SPECS,
                    RISK_TRACKING,
                    PRIORITIZATION,
                    SQL_STORYTELLING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Process improvement",
                        "Mapping without a change in wait time or error rate is theater.",
                        "Pick one delay in a mapped process, change it, and measure the new wait.",
                    ),
                    skill(
                        "Systems analysis",
                        "Most 'we need a new tool' requests are an unowned workflow.",
                        "For one pain, list current systems, the gap, and whether config beats a new vendor.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "project-manager",
        "Project Manager",
        aliases=["IT Project Manager", "Delivery Manager", "Project Lead"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Scope and timeline",
                        "A project without a written in/out list will absorb every adjacent request.",
                        "Write a one-page charter: outcome, in/out, milestone dates, and sponsor.",
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
                        "The job is making hidden work and owners visible.",
                        "Publish a RACI for one milestone and resolve the first owner conflict in writing.",
                    ),
                    skill(
                        "Status reporting",
                        "Status that hides red items until the week of launch is how projects fail publicly.",
                        "Write a status with green/yellow/red, the date it changed, and the decision needed.",
                    ),
                    PRIORITIZATION,
                    PRODUCT_SPECS,
                    FORECASTING,
                    skill(
                        "Budget tracking",
                        "Surprise overruns are usually untracked vendor and overtime costs.",
                        "Reconcile one project's planned vs actual spend and name the largest variance cause.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Change control",
                        "Scope change is allowed; silent scope change is not.",
                        "Run one change request with impact on date, cost, and what will be dropped.",
                    ),
                    NEGOTIATION,
                    RISK_TRACKING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "scrum-master",
        "Scrum Master",
        aliases=["Agile Coach", "Iteration Manager", "Delivery Coach"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Agile facilitation",
                        "Ceremonies without a purpose become status theater.",
                        "Facilitate one standup that surfaces a blocker and an owner, not a tour of tickets.",
                    ),
                    COLLABORATION,
                    DOCUMENTATION,
                    STAKEHOLDER_COMMUNICATION,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Impediment removal",
                        "A scrum master who only books meetings is a calendar bot.",
                        "Take one blocker to the person who can actually clear it and write the outcome.",
                    ),
                    skill(
                        "Team metrics without weaponizing them",
                        "Velocity as a performance score destroys honesty.",
                        "Use one flow metric (cycle time or WIP) to ask a process question, not to rate people.",
                    ),
                    skill(
                        "Coaching without doing the work",
                        "Taking the keyboard trains the team to wait for you.",
                        "Coach one teammate through a refinement question instead of answering it for them.",
                    ),
                    PRODUCT_SPECS,
                    RISK_TRACKING,
                    PROCESS_MAPPING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Org-level agility",
                        "One team cannot be agile inside a quarterly big-bang funding model without translation.",
                        "Write the constraints your team cannot change and the working agreements that still help.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    NEGOTIATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "financial-analyst",
        "Financial Analyst",
        aliases=["FP&A Analyst", "Finance Analyst", "Corporate Financial Analyst"],
        stages=[
            stage(
                "Foundations",
                [
                    FINANCIAL_MODELING,
                    SQL,
                    skill(
                        "Financial reporting literacy",
                        "If you cannot read the statements, your model will not survive a review.",
                        "Walk one P&L and balance sheet and write how a hiring plan would show up.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Business partnering",
                        "A model nobody uses is a spreadsheet hobby.",
                        "Sit with one operator, translate their plan into drivers, and send the assumptions back for sign-off.",
                    ),
                    FORECASTING,
                    SQL_STORYTELLING,
                    PRIORITIZATION,
                    RISK_TRACKING,
                    skill(
                        "Variance analysis",
                        "A miss without a driver is not an explanation.",
                        "Explain one variance with volume, rate, and timing, not a single 'timing' handwave.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Valuation and investment cases",
                        "A hire or capex request needs a case, not a vibe.",
                        "Write a one-page investment case with payback, risks, and what would kill the project.",
                    ),
                    NEGOTIATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "accountant",
        "Accountant",
        aliases=["Staff Accountant", "Senior Accountant", "Financial Accountant"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Double-entry bookkeeping",
                        "Every debit has a credit; mystery balances are unposted or misclassified entries.",
                        "Record a week of sample transactions and prove the trial balance.",
                    ),
                    skill(
                        "Reconciliations",
                        "Unreconciled accounts are how errors and fraud hide.",
                        "Complete one bank or subledger reconciliation with every difference explained.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Month-end close",
                        "A close that depends on heroics will slip and then be restated.",
                        "Own one close checklist item with a cutoff, owner, and review.",
                    ),
                    skill(
                        "Controls and documentation",
                        "If only one person can explain an entry, you have a key-person risk.",
                        "Write the procedure for one recurring journal including system, approver, and evidence.",
                    ),
                    RISK_TRACKING,
                    SQL,
                    PRIORITIZATION,
                    FINANCIAL_MODELING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Technical accounting judgment",
                        "New contracts and leases need a policy, not an improvised spreadsheet.",
                        "Write the issue, literature you would consult, and the conclusion for one gray-area item (training, not advice).",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    FORECASTING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "hr-generalist",
        "HR Generalist",
        aliases=[
            "People Operations",
            "HR Business Partner",
            "People Partner",
            "Human Resources Generalist",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    EMPLOYMENT_LAW,
                    skill(
                        "Employee relations",
                        "Undocumented conversations become he-said-she-said cases.",
                        "Write a factual summary of one workplace issue with dates, policy, and next step.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "HR data and reporting",
                        "Headcount and leave data that does not match payroll will be distrusted immediately.",
                        "Reconcile one HR report to a source system and document the definition.",
                    ),
                    skill(
                        "Performance management systems",
                        "A process nobody understands will be gamed or ignored.",
                        "Explain one cycle (goals, review, calibration) in one page a manager can follow.",
                    ),
                    SOURCING,
                    RISK_TRACKING,
                    NEGOTIATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Org and manager coaching",
                        "HR that only polices forms does not improve teams.",
                        "Coach one manager through a difficult conversation with a written plan, not a script dumped on them.",
                    ),
                    FORECASTING,
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "technical-recruiter",
        "Technical Recruiter",
        aliases=[
            "Tech Recruiter",
            "Technical Sourcer",
            "Talent Acquisition Partner",
            "Recruiting Coordinator",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Technical role and skill fluency",
                        "You cannot screen what you cannot describe; candidates notice faked fluency.",
                        "Write a one-page explainer for one role: problems they solve, tools, and seniority signals.",
                    ),
                    SOURCING,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Candidate experience",
                        "Slow, opaque processes lose the people you wanted.",
                        "Map one loop's delays and cut or explain the longest wait.",
                    ),
                    skill(
                        "Intake and scorecards",
                        "Hiring without a scorecard is vibes, then surprise rejects.",
                        "Run an intake that produces must-have evidence, not a twelve-tool wish list.",
                    ),
                    NEGOTIATION,
                    PRIORITIZATION,
                    FORECASTING,
                    EMPLOYMENT_LAW,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Offer negotiation",
                        "Surprise compensation conversations at offer stage waste weeks.",
                        "Align band, level, and non-salary constraints with the hiring manager before the final interview.",
                    ),
                    skill(
                        "Pipeline analytics",
                        "If you cannot say where candidates drop, you cannot fix it.",
                        "Report conversion by stage for one role and name the drop you will attack first.",
                    ),
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "revenue-operations",
        "Revenue Operations",
        aliases=["RevOps", "Sales Operations", "Revenue Analyst", "GTM Operations"],
        stages=[
            stage(
                "Foundations",
                [
                    SQL,
                    FORECASTING,
                    PROCESS_MAPPING,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "CRM data quality",
                        "Forecasts built on junk stages are fiction.",
                        "Define stage exit criteria for one pipeline and clean twenty violating records.",
                    ),
                    skill(
                        "Routing and SLA",
                        "Leads that sit die; routing rules are a product.",
                        "Document who owns a lead, the clock, and the fallback when the owner is out.",
                    ),
                    SQL_STORYTELLING,
                    PRIORITIZATION,
                    RISK_TRACKING,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Compensation and capacity models",
                        "Quota that ignores capacity creates burnout and sandbagging.",
                        "Build a simple capacity model: ramps, ramp time, and attainable quota.",
                    ),
                    FINANCIAL_MODELING,
                    NEGOTIATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "compliance-analyst",
        "Compliance Analyst",
        aliases=["GRC Analyst", "Risk and Compliance Analyst", "Controls Analyst"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Control mapping",
                        "A policy nobody can map to a control is a poster.",
                        "Map one policy statement to a control, owner, and evidence source.",
                    ),
                    DOCUMENTATION,
                    RISK_TRACKING,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    PROCESS_MAPPING,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Evidence collection",
                        "Audits fail on missing timestamps and screenshots of the wrong environment.",
                        "Collect one control's evidence with system, date, and who generated it.",
                    ),
                    skill(
                        "Issue management",
                        "Findings without due dates and owners return next year.",
                        "Log one issue with residual risk, owner, and a dated mitigation.",
                    ),
                    PRIORITIZATION,
                    SQL,
                    EMPLOYMENT_LAW,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Risk reporting",
                        "Leadership needs residual risk, not a CSV of every observation.",
                        "Write a one-page risk summary with trend and the decision you need.",
                    ),
                    FORECASTING,
                    NEGOTIATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
]
