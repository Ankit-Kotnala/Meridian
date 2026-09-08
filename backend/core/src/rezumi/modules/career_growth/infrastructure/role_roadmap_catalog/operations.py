"""Operations, supply chain, and workplace roles."""

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
    FORECASTING,
    HIRING_MARKET_SKILLS,
    INVENTORY,
    NEGOTIATION,
    PRIORITIZATION,
    PROCESS_MAPPING,
    PRODUCT_SPECS,
    RISK_TRACKING,
    SQL,
    SQL_STORYTELLING,
    STAKEHOLDER_COMMUNICATION,
)

OPERATIONS_ROLES: list[dict[str, Any]] = [
    role(
        "operations-manager",
        "Operations Manager",
        aliases=[
            "Business Operations Manager",
            "Ops Manager",
            "Chief of Staff",
            "Business Operations",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    PROCESS_MAPPING,
                    PRIORITIZATION,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    skill(
                        "Vendor and resource management",
                        "Unowned vendors create surprise bills and surprise outages.",
                        "List vendors for one function with owner, renewal date, and what happens if they fail.",
                    ),
                ],
            ),
            stage(
                "Core skills",
                [
                    FORECASTING,
                    RISK_TRACKING,
                    SQL_STORYTELLING,
                    skill(
                        "Operating cadence",
                        "If the weekly meeting has no decision, it is a status tax.",
                        "Redesign one recurring meeting with a purpose, pre-read, and a decision log.",
                    ),
                    PRODUCT_SPECS,
                    NEGOTIATION,
                    SQL,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Capacity and hiring plans",
                        "Headcount requests without workload math get cut, then the team burns out.",
                        "Build a simple capacity view: demand, current FTE, and the work you will stop if you do not hire.",
                    ),
                    INVENTORY,
                    FORECASTING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "supply-chain-analyst",
        "Supply Chain Analyst",
        aliases=[
            "Supply Chain Planner",
            "Logistics Analyst",
            "Demand Planner",
            "Inventory Analyst",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    INVENTORY,
                    SQL,
                    FORECASTING,
                    PROCESS_MAPPING,
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Demand forecasting",
                        "A forecast without error measurement will be blamed, then ignored.",
                        "Compare last period's forecast to actuals and report bias and the largest miss.",
                    ),
                    skill(
                        "Supplier performance",
                        "Late POs without a scorecard become folklore.",
                        "Track on-time and quality for one supplier and the action when they miss.",
                    ),
                    skill(
                        "Logistics cost optimization",
                        "Expedites hide a planning problem as a freight line.",
                        "Attribute one month of expedite cost to the cause (forecast, supplier, or process).",
                    ),
                    RISK_TRACKING,
                    STAKEHOLDER_COMMUNICATION,
                    SQL_STORYTELLING,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Network and scenario planning",
                        "Single-source and single-node networks fail in one incident.",
                        "Write a scenario: if one node is down for two weeks, what ships and what does not.",
                    ),
                    NEGOTIATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "customer-support-specialist",
        "Customer Support Specialist",
        aliases=[
            "Customer Support",
            "Support Agent",
            "Customer Service Specialist",
            "Technical Support Agent",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Ticket hygiene",
                        "A ticket without product, steps, and impact cannot be solved or escalated.",
                        "Rewrite five tickets with environment, steps, and what you already tried.",
                    ),
                    skill(
                        "Customer communication under pressure",
                        "Users in an outage need status and next step, not jargon.",
                        "Write a three-sentence update: impact, workaround, next update time.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    PROCESS_MAPPING,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Product troubleshooting",
                        "Guessing resets wastes the customer's time and yours.",
                        "Build a decision tree for one top issue and have a teammate follow it.",
                    ),
                    skill(
                        "Knowledge base writing",
                        "If only you can fix a repeating issue, you will never leave the queue.",
                        "Publish one article with symptoms, cause, and exact fix.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    SQL_STORYTELLING,
                    RISK_TRACKING,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Voice of customer",
                        "Support themes that never reach product will return next quarter.",
                        "Send one monthly theme brief with volume, example, and a product decision asked.",
                    ),
                    FORECASTING,
                    NEGOTIATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "implementation-specialist",
        "Implementation Specialist",
        aliases=[
            "Onboarding Specialist",
            "Customer Implementation Manager",
            "Professional Services Consultant",
            "Implementation Consultant",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    PROCESS_MAPPING,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    PRODUCT_SPECS,
                    skill(
                        "Discovery for implementation",
                        "Implementing the default setup into a unique process creates a failed go-live.",
                        "Write the customer's current process and the three ways it differs from your defaults.",
                    ),
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Project plan to go-live",
                        "Go-lives slip when data migration and training are afterthoughts.",
                        "Publish a plan with data, config, training, and a rollback owner.",
                    ),
                    RISK_TRACKING,
                    PRIORITIZATION,
                    NEGOTIATION,
                    SQL,
                    skill(
                        "Training and change",
                        "A feature nobody was trained on will be called a product bug.",
                        "Run one enablement session with a job-to-be-done and a practice task, not a feature tour.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Scope control",
                        "Every 'quick custom' becomes an unowned fork.",
                        "Write a change request with impact on date and whether it is config or custom.",
                    ),
                    FORECASTING,
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "executive-assistant",
        "Executive Assistant",
        aliases=["EA", "Chief of Staff Assistant", "Executive Coordinator"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Calendar and priority defense",
                        "An executive calendar without a priority rule fills with other people's urgencies.",
                        "Write the rules for what gets on the calendar and what gets a no.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    PRIORITIZATION,
                    PROCESS_MAPPING,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Meeting operations",
                        "Meetings without a purpose, pre-read, and notes waste the room.",
                        "Own one recurring meeting: agenda, notes, and tracked decisions.",
                    ),
                    skill(
                        "Travel and logistics under change",
                        "Plans break; the skill is a documented backup, not last-minute panic.",
                        "Write a travel packet with contacts, constraints, and the backup if a leg cancels.",
                    ),
                    RISK_TRACKING,
                    NEGOTIATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Information routing",
                        "Executives fail when the wrong detail arrives too late or too raw.",
                        "Create a weekly brief template: decisions needed, risks, and what can wait.",
                    ),
                    FORECASTING,
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "salesforce-administrator",
        "Salesforce Administrator",
        aliases=["CRM Administrator", "Salesforce Admin", "HubSpot Administrator", "RevOps Admin"],
        stages=[
            stage(
                "Foundations",
                [
                    PROCESS_MAPPING,
                    DOCUMENTATION,
                    COLLABORATION,
                    STAKEHOLDER_COMMUNICATION,
                    skill(
                        "CRM data model",
                        "Wrong objects and duplicate records make every report a debate.",
                        "Draw objects and relationships for one process and the unique keys you will enforce.",
                    ),
                    SQL,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Automation without chaos",
                        "Stacked flows that nobody owns will lock users out of saving records.",
                        "Document one automation: trigger, criteria, and how to turn it off.",
                    ),
                    skill(
                        "Permissions and sharing",
                        "Over-broad access is a security issue; over-narrow access is a shadow-CRM issue.",
                        "Review one profile/permission set against least privilege for a real job.",
                    ),
                    PRIORITIZATION,
                    RISK_TRACKING,
                    PRODUCT_SPECS,
                    SQL_STORYTELLING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Release management for CRM",
                        "Clicking production changes on Friday is how weekends burn.",
                        "Move one change through sandbox, test, and a dated production window with a rollback.",
                    ),
                    FORECASTING,
                    NEGOTIATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
]
