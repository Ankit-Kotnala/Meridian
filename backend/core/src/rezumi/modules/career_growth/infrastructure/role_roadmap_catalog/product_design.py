"""Product, design, research, and content experience roles."""

from __future__ import annotations

from typing import Any

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.builders import (
    role,
    skill,
    stage,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.shared import (
    ACCESSIBILITY,
    COLLABORATION,
    DOCUMENTATION,
    EXPERIMENT_DESIGN,
    HIRING_MARKET_SKILLS,
    HTML_CSS,
    PRIORITIZATION,
    PRODUCT_SPECS,
    SQL_STORYTELLING,
    STAKEHOLDER_COMMUNICATION,
    USER_RESEARCH,
)

PRODUCT_DESIGN_ROLES: list[dict[str, Any]] = [
    role(
        "product-manager",
        "Product Manager",
        aliases=["PM", "Product Owner", "Digital Product Manager", "Technical Product Manager"],
        stages=[
            stage(
                "Foundations",
                [
                    PRODUCT_SPECS,
                    PRIORITIZATION,
                    USER_RESEARCH,
                    STAKEHOLDER_COMMUNICATION,
                    DOCUMENTATION,
                    COLLABORATION,
                    skill(
                        "Opportunity assessment",
                        "Building a feature nobody needed is the most expensive PM mistake.",
                        "Write a one-page opportunity: who hurts, current workaround, and how you will know it is solved.",
                    ),
                ],
            ),
            stage(
                "Core skills",
                [
                    EXPERIMENT_DESIGN,
                    SQL_STORYTELLING,
                    skill(
                        "Roadmap communication",
                        "A roadmap that is a list of dates without bets cannot be used by engineering or sales.",
                        "Publish themes, not a fake Gantt: problem, bet, and what would make you stop.",
                    ),
                    skill(
                        "Discovery interviews",
                        "Leading questions produce compliments, not product insight.",
                        "Run five interviews with a guide that asks about last time they did the job, not whether they like your idea.",
                    ),
                    skill(
                        "Metrics and analytics",
                        "If the success metric is 'engagement' with no definition, you cannot decide.",
                        "Pick one metric with a denominator and a counter-metric that would show harm.",
                    ),
                    skill(
                        "Working with engineering",
                        "PMs who skip constraints ship fiction.",
                        "Sit with one engineer on a design and write the constraint that changed the scope.",
                    ),
                    ACCESSIBILITY,
                    skill(
                        "Onboarding design",
                        "Activation is a product problem; dumping users into a blank app is not a launch.",
                        "Map first-run to first value for one persona and remove one unnecessary step.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Strategy and positioning",
                        "A backlog is not a strategy.",
                        "Write who the product is not for, and one competitor move you will ignore.",
                    ),
                    skill(
                        "Pricing and packaging basics",
                        "Packaging that does not match how buyers buy creates discounting later.",
                        "Map one package to a job-to-be-done and a constraint you will not discount away.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    PRIORITIZATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "product-designer",
        "Product Designer",
        aliases=["UX Designer", "UI Designer", "Product UX Designer", "Interaction Designer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Interaction design",
                        "Pretty screens that hide state and errors fail in real use.",
                        "Design one flow with empty, loading, error, and success, not only the hero mock.",
                    ),
                    HTML_CSS,
                    ACCESSIBILITY,
                    USER_RESEARCH,
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Design systems",
                        "One-off components do not scale across a product.",
                        "Contribute or consume one component with states, spacing, and usage notes.",
                    ),
                    skill(
                        "Design critique",
                        "Unspecific feedback ('make it pop') does not improve the work.",
                        "Give critique on one file using user goal, hierarchy, and accessibility, then revise.",
                    ),
                    skill(
                        "Prototyping",
                        "Stakeholders cannot evaluate a still image the way they evaluate a clickable path.",
                        "Prototype one critical path including the mistake a new user will make.",
                    ),
                    skill(
                        "Design-to-engineering",
                        "Handoff that omits states, copy, and breakpoints creates implementation lottery.",
                        "Annotate one file with all states and what is allowed to wrap on small screens.",
                    ),
                    PRODUCT_SPECS,
                    PRIORITIZATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Service and cross-channel design",
                        "Users do not experience your screens in isolation from email, support, and ops.",
                        "Map one journey across product and a non-product touch and fix the worst drop.",
                    ),
                    EXPERIMENT_DESIGN,
                    ACCESSIBILITY,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "ux-researcher",
        "UX Researcher",
        aliases=["User Researcher", "Design Researcher", "UX Research Specialist"],
        stages=[
            stage(
                "Foundations",
                [
                    USER_RESEARCH,
                    skill(
                        "Research ethics and consent",
                        "Recordings and quotes without consent are a trust and legal failure.",
                        "Write a consent script and data retention note for one study before you recruit.",
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
                        "Study design",
                        "The method has to match the decision; a survey cannot answer 'why did they stall'.",
                        "Pick a decision a team needs this month and choose a method that can actually inform it.",
                    ),
                    skill(
                        "Synthesis and affinity mapping",
                        "A slide of quotes is not a finding.",
                        "Group notes from one study into patterns with count, counter-example, and implication.",
                    ),
                    skill(
                        "Usability testing",
                        "Watching people fail is cheaper than shipping the wrong navigation.",
                        "Run five task-based sessions on one flow and log completion and where they hesitated.",
                    ),
                    skill(
                        "Research advocacy",
                        "Research that is not in the decision meeting did not happen.",
                        "Present one finding as a decision, options, and the evidence, not a 40-page appendix.",
                    ),
                    PRODUCT_SPECS,
                    EXPERIMENT_DESIGN,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Mixed methods",
                        "Qual without numbers, or numbers without stories, gets dismissed.",
                        "Pair one behavioral metric with interviews that explain a dip, and write the combined claim carefully.",
                    ),
                    PRIORITIZATION,
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "ux-writer",
        "UX Writer",
        aliases=["Content Designer", "Product Writer", "UX Content Designer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Microcopy and interface writing",
                        "Buttons, errors, and empty states are often the only content users read.",
                        "Rewrite five error messages or labels for clarity over cleverness.",
                    ),
                    skill(
                        "Voice and tone consistency",
                        "Inconsistent voice makes a product feel unowned.",
                        "Audit ten strings in one flow and flag every mismatch with the intended voice.",
                    ),
                    ACCESSIBILITY,
                    COLLABORATION,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Content testing",
                        "Copy the writer understands is often not copy the user understands.",
                        "Test two versions of one confusing string with a handful of people and keep the faster one.",
                    ),
                    skill(
                        "Collaborating with design and engineering",
                        "Writing decided in isolation gets overwritten by layout and validation constraints.",
                        "Join one design review before copy is locked and flag a constraint that changes the words.",
                    ),
                    skill(
                        "Content governance",
                        "Unowned strings drift; a source of truth and review path keeps them honest.",
                        "List where UI strings live for one product and who can change them.",
                    ),
                    PRODUCT_SPECS,
                    USER_RESEARCH,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Information architecture for content",
                        "Help centers and in-product education fail when structure mirrors the org chart.",
                        "Restructure one help path around a user job, not a department name.",
                    ),
                    EXPERIMENT_DESIGN,
                    PRIORITIZATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "graphic-designer",
        "Graphic Designer",
        aliases=["Visual Designer", "Brand Designer", "Communications Designer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Typography and layout",
                        "Most viewers notice spacing and type before they notice a clever idea.",
                        "Redesign one existing piece using only better type and spacing, no new imagery.",
                    ),
                    skill(
                        "Brand system application",
                        "Most professional work happens inside an existing brand, not a blank canvas.",
                        "Take one brand's guidelines and make three assets that clearly belong together.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    ACCESSIBILITY,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Design critique and iteration",
                        "First drafts are rarely the final answer; specific feedback is the job.",
                        "Share one design before you think it is finished and revise from the two most specific notes.",
                    ),
                    skill(
                        "Production-ready file preparation",
                        "A design that is not prepared for print or web causes costly rework.",
                        "Take one finished design through color, resolution, and export checks for its real channel.",
                    ),
                    skill(
                        "Motion and static hierarchy",
                        "Decoration that fights the message makes campaigns feel expensive and unclear.",
                        "Remove one decorative element from a piece and check whether the message got stronger.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Campaign systems",
                        "One beautiful one-off does not scale across ads, email, and landing pages.",
                        "Design a small system: three sizes, one idea, consistent type and color.",
                    ),
                    USER_RESEARCH,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "technical-writer",
        "Technical Writer",
        aliases=["Documentation Engineer", "Docs Writer", "Information Developer"],
        stages=[
            stage(
                "Foundations",
                [
                    DOCUMENTATION,
                    skill(
                        "Audience and task analysis",
                        "Docs written for the author fail the reader who is stuck on a specific task.",
                        "Rewrite one page as a task with prerequisites, steps, and verification.",
                    ),
                    COLLABORATION,
                    skill(
                        "Plain language",
                        "Jargon that is not defined is a support ticket later.",
                        "Edit one page to define terms on first use and cut filler.",
                    ),
                    ACCESSIBILITY,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Docs-as-code",
                        "Documentation that cannot be reviewed in the same pipeline as code will rot.",
                        "Put one guide in version control with a preview and a review checklist.",
                    ),
                    skill(
                        "Information architecture",
                        "If readers cannot find the page, the page does not exist.",
                        "Restructure one section around tasks and add a 'you are here' next-step at the end of each page.",
                    ),
                    skill(
                        "API reference quality",
                        "Missing error cases and examples make API docs unusable.",
                        "Document one endpoint with auth, example request, and the error a client will actually see.",
                    ),
                    PRODUCT_SPECS,
                    USER_RESEARCH,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Subject-matter collaboration",
                        "Writers who cannot extract knowledge from engineers ship guesses.",
                        "Interview one engineer with a question list and convert it into a verified procedure.",
                    ),
                    EXPERIMENT_DESIGN,
                    PRIORITIZATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "service-designer",
        "Service Designer",
        aliases=["Experience Designer", "CX Designer"],
        stages=[
            stage(
                "Foundations",
                [
                    USER_RESEARCH,
                    skill(
                        "Journey mapping",
                        "Service problems live in handoffs between teams, not in a single screen.",
                        "Map one journey with frontstage, backstage, and the owner of each step.",
                    ),
                    COLLABORATION,
                    DOCUMENTATION,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Blueprinting",
                        "A journey map without systems and policies cannot be implemented.",
                        "Add systems, policies, and SLAs to one journey and circle the first broken handoff.",
                    ),
                    PRODUCT_SPECS,
                    PRIORITIZATION,
                    ACCESSIBILITY,
                    EXPERIMENT_DESIGN,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Operating model change",
                        "Service design that does not change staffing, scripts, or metrics will not stick.",
                        "Propose one operating change (owner, metric, or script) required for a journey fix to survive.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
]
