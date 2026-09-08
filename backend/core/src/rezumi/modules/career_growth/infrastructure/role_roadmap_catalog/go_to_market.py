"""Go-to-market, sales, success, and marketing roles."""

from __future__ import annotations

from typing import Any

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.builders import (
    role,
    skill,
    stage,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.shared import (
    COLLABORATION,
    DISCOVERY,
    DOCUMENTATION,
    EXPERIMENT_DESIGN,
    FORECASTING,
    HIRING_MARKET_SKILLS,
    HTML_CSS,
    NEGOTIATION,
    PRIORITIZATION,
    PRODUCT_SPECS,
    SQL_STORYTELLING,
    STAKEHOLDER_COMMUNICATION,
)

GO_TO_MARKET_ROLES: list[dict[str, Any]] = [
    role(
        "sales-account-executive",
        "Account Executive",
        aliases=["Account Executive", "AE", "Enterprise Account Executive", "Sales Executive"],
        stages=[
            stage(
                "Foundations",
                [
                    DISCOVERY,
                    skill(
                        "Pipeline management",
                        "A pipeline that is not honestly staged produces quarter-end surprises.",
                        "Review every deal this week and move each to the stage it actually belongs in.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    NEGOTIATION,
                    FORECASTING,
                    skill(
                        "Multi-threaded selling",
                        "Single-threaded deals die when one champion goes on leave.",
                        "Map economic buyer, champion, and blocker for one opportunity and book the missing meeting.",
                    ),
                    skill(
                        "Mutual action plans",
                        "Deals stall when next steps live only in the seller's head.",
                        "Write a shared close plan with dates both sides can see.",
                    ),
                    PRODUCT_SPECS,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Enterprise process and procurement",
                        "Security review and legal are the deal, not a surprise at the end.",
                        "List the buyer's process for one deal and the artifact each stage needs from you.",
                    ),
                    skill(
                        "Account planning",
                        "Hunting only new logos leaves expansion and churn unmanaged.",
                        "Write a 90-day plan for one account: land, expand, risk.",
                    ),
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "sales-development-representative",
        "Sales Development Representative",
        aliases=["SDR", "BDR", "Business Development Representative", "Sales Development"],
        stages=[
            stage(
                "Foundations",
                [
                    DISCOVERY,
                    skill(
                        "Outbound research",
                        "Generic sequences get ignored; relevant context gets replies.",
                        "Write ten personalized openers that cite a public fact about the account, not a compliment.",
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
                        "Qualification",
                        "Passing unqualified meetings burns AE time and your reputation.",
                        "Apply a written qualification checklist before every handoff this week.",
                    ),
                    skill(
                        "Objection handling on first touch",
                        "Early 'not interested' is often timing or the wrong person, not a closed door.",
                        "Write replies for the five objections you actually hear, including when to stop.",
                    ),
                    skill(
                        "CRM hygiene",
                        "A dirty CRM makes forecasting and routing lies.",
                        "Clean twenty records: next step, date, and a reason code, not 'following up'.",
                    ),
                    PRIORITIZATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Territory and ICP discipline",
                        "Spraying every logo in the TAM is not a strategy.",
                        "Define ICP must-haves and stop outbound to accounts that fail two of them.",
                    ),
                    EXPERIMENT_DESIGN,
                    FORECASTING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "customer-success-manager",
        "Customer Success Manager",
        aliases=["CSM", "Customer Success", "Account Manager", "Renewal Manager"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Account health",
                        "Surprise churn is usually a health signal nobody wrote down.",
                        "Define red/yellow/green for five accounts with product usage and relationship evidence.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    DOCUMENTATION,
                    COLLABORATION,
                    DISCOVERY,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Onboarding to value",
                        "Customers who never reach first value do not renew, no matter how friendly QBR slides are.",
                        "Write a time-to-value path for one segment with owners and a week-four check.",
                    ),
                    skill(
                        "QBR and executive communication",
                        "Status meetings that recap tickets waste the only exec time you get.",
                        "Run one review around outcomes, risk, and a decision, not a feature tour.",
                    ),
                    NEGOTIATION,
                    FORECASTING,
                    PRODUCT_SPECS,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Expansion and advocacy",
                        "Healthy accounts still need a reason to buy more; silence is not a land-and-expand plan.",
                        "Write an expansion hypothesis for one account tied to a job they already do.",
                    ),
                    skill(
                        "Churn forensics",
                        "If you cannot name why the last three logos left, you will repeat it.",
                        "Review three lost accounts and group causes into product, process, or relationship.",
                    ),
                    SQL_STORYTELLING,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "marketing-manager",
        "Marketing Manager",
        aliases=["Brand Manager", "Product Marketing Manager", "Marketing Lead"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Positioning",
                        "If you cannot say who it is for and why they should care in one sentence, campaigns will thrash.",
                        "Write positioning for one offering: audience, alternative, and the proof you actually have.",
                    ),
                    skill(
                        "Audience and content",
                        "Content without an audience job becomes a blog nobody asked for.",
                        "Map one content piece to a job, channel, and a measurable next step.",
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
                        "Campaign planning",
                        "A campaign is a sequence with a goal, not a burst of posts.",
                        "Write a campaign brief: audience, offer, channels, budget, and the one success metric.",
                    ),
                    EXPERIMENT_DESIGN,
                    SQL_STORYTELLING,
                    PRIORITIZATION,
                    PRODUCT_SPECS,
                    skill(
                        "Channel-specific execution",
                        "Copy that works in a blog fails in ads and email.",
                        "Adapt one message to two channels and measure which one earned the action.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Retention and lifecycle",
                        "Acquisition without lifecycle is a leaky bucket.",
                        "Design one lifecycle series for a segment with an unsubscribe-respecting stop rule.",
                    ),
                    FORECASTING,
                    skill(
                        "Budget and mix",
                        "Spending without a hypothesis cannot be cut or scaled intelligently.",
                        "Allocate one month of spend to two channels with a kill rule for the loser.",
                    ),
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "growth-marketer",
        "Growth Marketer",
        aliases=["Growth Manager", "Growth Lead", "Performance Marketer"],
        stages=[
            stage(
                "Foundations",
                [
                    EXPERIMENT_DESIGN,
                    SQL_STORYTELLING,
                    skill(
                        "Funnel instrumentation",
                        "You cannot grow what you cannot measure at each step.",
                        "Define events for one signup-to-value path and check they actually fire.",
                    ),
                    COLLABORATION,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Acquisition experiments",
                        "Copying a competitor's landing page is not a test.",
                        "Ship one landing or onboarding test with a pre-registered metric and sample rule.",
                    ),
                    skill(
                        "Retention loops",
                        "Paid acquisition without a reason to return is rented growth.",
                        "Identify one habit or notification that brings users back for a job they already have.",
                    ),
                    PRIORITIZATION,
                    PRODUCT_SPECS,
                    STAKEHOLDER_COMMUNICATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Attribution humility",
                        "Last-click stories will overfund a channel and starve another.",
                        "Compare two attribution views for one month and write what you still do not know.",
                    ),
                    FORECASTING,
                    EXPERIMENT_DESIGN,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "seo-specialist",
        "SEO Specialist",
        aliases=["SEO Manager", "Search Engine Optimizer", "Organic Search Specialist"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Keyword and intent research",
                        "Ranking for a query nobody has, or the wrong intent, wastes the page.",
                        "Build a small keyword set with intent and a page type for each.",
                    ),
                    skill(
                        "On-page SEO",
                        "Titles, headings, and crawlable content still decide whether a page can rank.",
                        "Fix titles, headings, and internal links on one important URL.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                    HTML_CSS,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Technical SEO",
                        "Indexation, canonicals, and speed problems cannot be fixed with more blog posts.",
                        "Audit one site for indexation and Core Web Vitals, then file the highest-impact fix.",
                    ),
                    skill(
                        "Link building ethics",
                        "Spam links create penalty risk; relevant citations take longer and last.",
                        "Earn or document one relevant citation and refuse one shortcut you would not defend.",
                    ),
                    skill(
                        "Content brief quality",
                        "Writers cannot rank for intent they were not briefed on.",
                        "Write one brief with search intent, outline, internal links, and a unique angle you can actually support.",
                    ),
                    EXPERIMENT_DESIGN,
                    SQL_STORYTELLING,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "International and site architecture",
                        "Duplicate locales and buried pages waste crawl budget.",
                        "Map one site's important templates and the crawl path to the money pages.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "content-strategist",
        "Content Strategist",
        aliases=["Content Manager", "Editorial Strategist", "Content Lead"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Editorial planning",
                        "A calendar of random topics is not a strategy.",
                        "Plan four weeks of content against one audience job and one business goal.",
                    ),
                    skill(
                        "Voice and tone",
                        "Inconsistent voice makes a brand feel unstaffed.",
                        "Write a one-page voice guide with examples of yes and no.",
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
                        "Content operations",
                        "Briefs, reviews, and updates need owners or the library rots.",
                        "Define the workflow for one content type: draft, review, publish, refresh date.",
                    ),
                    skill(
                        "Measurement",
                        "Traffic without a next step is vanity.",
                        "Pick one piece and name the action it should cause, then report whether it did.",
                    ),
                    EXPERIMENT_DESIGN,
                    PRIORITIZATION,
                    PRODUCT_SPECS,
                    SQL_STORYTELLING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Content governance",
                        "Outdated pages create support and legal risk.",
                        "Audit ten URLs for accuracy and unpublish or refresh the worst two.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    PRIORITIZATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "community-manager",
        "Community Manager",
        aliases=["Community Lead", "Developer Community Manager"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Community moderation",
                        "An unmoderated space becomes unsafe and then empty.",
                        "Write public rules and a response path for the two most likely harmful behaviors.",
                    ),
                    STAKEHOLDER_COMMUNICATION,
                    DOCUMENTATION,
                    COLLABORATION,
                    PRIORITIZATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Program design",
                        "Random events do not create belonging; repeating rituals do.",
                        "Run one recurring program with a purpose, host, and how you will know it worked.",
                    ),
                    skill(
                        "Feedback loops to product",
                        "Community insight that never reaches the product team is entertainment.",
                        "Deliver one monthly insight brief with count, examples, and a decision asked.",
                    ),
                    PRODUCT_SPECS,
                    EXPERIMENT_DESIGN,
                    SQL_STORYTELLING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Crisis communication",
                        "Silence during an incident is a community decision.",
                        "Write a holding statement template: impact, what you know, when you update next.",
                    ),
                    NEGOTIATION,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
]
