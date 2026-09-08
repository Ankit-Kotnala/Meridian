"""Data, analytics, and AI role roadmaps."""

from __future__ import annotations

from typing import Any

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.builders import (
    role,
    skill,
    stage,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.shared import (
    CICD,
    CLOUD_FUNDAMENTALS,
    COLLABORATION,
    CONTAINERS,
    DOCUMENTATION,
    EXPERIMENT_DESIGN,
    HIRING_MARKET_SKILLS,
    INCIDENT_RESPONSE,
    LINUX,
    MACHINE_LEARNING,
    OBSERVABILITY,
    PRODUCT_SPECS,
    PYTHON,
    RELATIONAL_DATABASES,
    SECURITY_BASICS,
    SQL,
    SQL_STORYTELLING,
    STATISTICS,
    SYSTEM_DESIGN,
    TESTING,
    VERSION_CONTROL,
)

DATA_AI_ROLES: list[dict[str, Any]] = [
    role(
        "data-scientist",
        "Data Scientist",
        aliases=["Applied Scientist", "Research Data Scientist"],
        stages=[
            stage(
                "Foundations",
                [
                    PYTHON,
                    SQL,
                    STATISTICS,
                    skill(
                        "Data wrangling",
                        "Most analysis time is cleaning joins, nulls, and leaky timestamps, not fitting models.",
                        "Take one messy public table and produce a documented clean table with tests for row counts.",
                    ),
                    VERSION_CONTROL,
                    DOCUMENTATION,
                    EXPERIMENT_DESIGN,
                ],
            ),
            stage(
                "Core skills",
                [
                    MACHINE_LEARNING,
                    SQL_STORYTELLING,
                    skill(
                        "Feature thinking",
                        "Models fail when features leak the future or encode the label.",
                        "For one prediction task, list features, leakage risk, and a baseline without the model.",
                    ),
                    skill(
                        "Experiment analysis",
                        "A significant p-value with a broken assignment mechanism is still a wrong decision.",
                        "Analyze one A/B with assignment checks, metric window, and a pre-registered success rule.",
                    ),
                    TESTING,
                    COLLABORATION,
                    PRODUCT_SPECS,
                    skill(
                        "Reproducible notebooks and pipelines",
                        "A result that cannot be rerun is not a result a product team can ship.",
                        "Pin dependencies and seed one analysis so a teammate can reproduce the number.",
                    ),
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Model evaluation in production",
                        "Offline scores are not user impact; monitoring and delayed labels are the job after launch.",
                        "Define offline metric, online metric, and a kill switch for one model.",
                    ),
                    skill(
                        "Causal inference basics",
                        "Stakeholders ask what would change if X changed; correlation-only answers get misused.",
                        "Write identification assumptions for one causal question and the design you would actually run.",
                    ),
                    SYSTEM_DESIGN,
                    SECURITY_BASICS,
                    OBSERVABILITY,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "data-engineer",
        "Data Engineer",
        aliases=["Analytics Engineer", "ETL Engineer", "Data Platform Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    SQL,
                    PYTHON,
                    RELATIONAL_DATABASES,
                    VERSION_CONTROL,
                    LINUX,
                    TESTING,
                    DOCUMENTATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Data pipeline orchestration",
                        "Pipelines fail overnight; retries, backfills, and alerting are the job.",
                        "Build one scheduled pipeline with a retry, a data-quality check, and an owner alert.",
                    ),
                    skill(
                        "Data modeling",
                        "A warehouse that is a dump of production tables cannot be used by analysts safely.",
                        "Design a star or similar model for one business process with grain and unique keys.",
                    ),
                    skill(
                        "ETL and ELT",
                        "Transform location and freshness tradeoffs decide cost and trust.",
                        "Document extract, load, and transform for one source including late-arriving data.",
                    ),
                    skill(
                        "Data quality",
                        "Silent nulls and duplicated grains destroy dashboards and ML features.",
                        "Add tests for uniqueness, not-null, and accepted values on one critical table.",
                    ),
                    CICD,
                    CLOUD_FUNDAMENTALS,
                    OBSERVABILITY,
                    COLLABORATION,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Streaming vs batch",
                        "Not every problem needs streaming; the ones that do fail differently.",
                        "Write a one-page choice for one dataset: batch window vs stream, with failure modes.",
                    ),
                    SYSTEM_DESIGN,
                    SECURITY_BASICS,
                    skill(
                        "Cost and warehouse performance",
                        "Unbounded scans are a finance incident.",
                        "Explain one expensive query and change clustering, partitioning, or the model to reduce it.",
                    ),
                    CONTAINERS,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "ai-engineer",
        "AI Engineer",
        aliases=[
            "Artificial Intelligence Engineer",
            "Applied AI Engineer",
            "Generative AI Engineer",
            "LLM Engineer",
            "AI Application Engineer",
            "AI/ML Engineer",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Python for AI applications",
                        "Production AI work depends on inspecting data, integrating model libraries, and writing reliable application code.",
                        "Build one small Python service that validates input, calls a model through a narrow interface, and tests the response shape.",
                    ),
                    MACHINE_LEARNING,
                    PYTHON,
                    SQL,
                    VERSION_CONTROL,
                    TESTING,
                    DOCUMENTATION,
                    SECURITY_BASICS,
                ],
            ),
            stage(
                "Core systems",
                [
                    skill(
                        "LLM application architecture",
                        "Useful AI products need orchestration, validation, failure handling, and observability around model calls.",
                        "Diagram one AI feature as validation, context construction, model call, structured checks, and fallback.",
                    ),
                    skill(
                        "Retrieval-augmented generation",
                        "Retrieval can ground answers only when chunking, search quality, citations, and access rules are designed together.",
                        "Create a small retrieval prototype, then measure whether retrieved passages actually support each answer.",
                    ),
                    skill(
                        "AI evaluation and test design",
                        "Model output varies, so a fixed test set and explicit quality, safety, latency, and cost checks are required.",
                        "Write twenty representative cases, define pass criteria before testing, and record regressions by category.",
                    ),
                    skill(
                        "Prompt design with contracts",
                        "Unstructured prompts hide breaking changes; schemas and golden tests make model calls reviewable.",
                        "Replace one free-form prompt with a schema, examples, and a failing test when the schema breaks.",
                    ),
                    OBSERVABILITY,
                    SYSTEM_DESIGN,
                    PRODUCT_SPECS,
                    COLLABORATION,
                ],
            ),
            stage(
                "Production practice",
                [
                    skill(
                        "Responsible AI and safety controls",
                        "AI systems must handle unsupported claims, unsafe inputs, privacy, and human review as product requirements.",
                        "Threat-model one AI workflow and add a deterministic refusal or review path for the highest-impact risk.",
                    ),
                    skill(
                        "Model serving, monitoring, and cost controls",
                        "A production AI feature must stay observable when providers slow down, outputs drift, or usage grows.",
                        "Instrument one model-backed endpoint with latency, error, usage, and validation metrics plus a fallback.",
                    ),
                    CICD,
                    CLOUD_FUNDAMENTALS,
                    INCIDENT_RESPONSE,
                    skill(
                        "Human review and escalation",
                        "Some AI outputs must not go to users without a person; that path has to be designed, not hoped for.",
                        "Add a review queue for one high-impact output type and measure time-to-review.",
                    ),
                ],
            ),
        ],
    ),
    role(
        "ml-engineer",
        "Machine Learning Engineer",
        aliases=["ML Engineer", "MLOps Engineer", "Machine Learning Platform Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    skill(
                        "Applied machine learning fundamentals",
                        "ML engineering builds on core ML concepts even when the job is mostly infrastructure.",
                        "Train and evaluate one simple model end-to-end on a public dataset before touching deployment tooling.",
                    ),
                    PYTHON,
                    SQL,
                    STATISTICS,
                    VERSION_CONTROL,
                    TESTING,
                    LINUX,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Model deployment and serving",
                        "A model that only runs in a notebook delivers no value.",
                        "Wrap one trained model behind a simple API and load-test it.",
                    ),
                    skill(
                        "ML pipeline reproducibility",
                        "Without versioned data, code, and models, a result that worked once cannot be trusted later.",
                        "Add data and model versioning to one training script so a past result can be reproduced.",
                    ),
                    CICD,
                    CONTAINERS,
                    CLOUD_FUNDAMENTALS,
                    OBSERVABILITY,
                    COLLABORATION,
                    MACHINE_LEARNING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Model monitoring and drift detection",
                        "Model performance degrades silently as live data shifts away from training data.",
                        "Set up a monitor comparing live prediction distributions against training-time distributions.",
                    ),
                    SYSTEM_DESIGN,
                    SECURITY_BASICS,
                    INCIDENT_RESPONSE,
                    skill(
                        "Feature stores and training-serving skew",
                        "Training on one pipeline and serving another is a classic silent failure.",
                        "Document feature computation for one model in training and in serving, and name any mismatch.",
                    ),
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "data-analyst",
        "Data Analyst",
        aliases=[
            "Business Intelligence Analyst",
            "BI Analyst",
            "Insights Analyst",
            "Reporting Analyst",
        ],
        stages=[
            stage(
                "Foundations",
                [
                    SQL,
                    STATISTICS,
                    SQL_STORYTELLING,
                    skill(
                        "Spreadsheet analysis",
                        "Many stakeholder questions still start in a spreadsheet; messy sheets hide wrong totals.",
                        "Rebuild one report with documented filters, a totals check, and no hidden rows.",
                    ),
                    DOCUMENTATION,
                    COLLABORATION,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "KPI definition",
                        "A dashboard without a written definition will be argued instead of used.",
                        "Write the definition, grain, and exclusion rules for one KPI and get a stakeholder to confirm it.",
                    ),
                    skill(
                        "Funnel and cohort analysis",
                        "Point-in-time totals hide whether the same users progress or a new crowd arrived.",
                        "Build one funnel with a cohort window and a note about users who never enter.",
                    ),
                    skill(
                        "Data visualization",
                        "Chart junk and truncated axes create false urgency.",
                        "Redesign one chart so the claim, comparison, and time window are readable without a meeting.",
                    ),
                    EXPERIMENT_DESIGN,
                    PRODUCT_SPECS,
                    SQL,
                    TESTING,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Self-serve semantic layers",
                        "If every question needs the analyst, the company will invent competing numbers.",
                        "Publish one certified dataset with grain, owners, and example questions it can and cannot answer.",
                    ),
                    SECURITY_BASICS,
                    OBSERVABILITY,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
    role(
        "research-scientist",
        "Research Scientist",
        aliases=["Applied Research Scientist", "Research Engineer"],
        stages=[
            stage(
                "Foundations",
                [
                    PYTHON,
                    STATISTICS,
                    MACHINE_LEARNING,
                    DOCUMENTATION,
                    VERSION_CONTROL,
                    EXPERIMENT_DESIGN,
                ],
            ),
            stage(
                "Core skills",
                [
                    skill(
                        "Literature and baselines",
                        "A method without a baseline and related work is a demo, not research.",
                        "Reproduce one published baseline on a public dataset and record where your numbers differ.",
                    ),
                    skill(
                        "Experimental rigor",
                        "Unseeded runs and unreported splits make results unreproducible.",
                        "Write a protocol for one experiment: data split, seeds, metrics, and stop rule.",
                    ),
                    TESTING,
                    SQL,
                    COLLABORATION,
                    PRODUCT_SPECS,
                ],
            ),
            stage(
                "Advanced",
                [
                    skill(
                        "Research to product transfer",
                        "A paper metric that cannot run in the product's latency or data constraints will not ship.",
                        "Write constraints for one idea: latency, data access, and what would falsify it in production.",
                    ),
                    SYSTEM_DESIGN,
                    SECURITY_BASICS,
                    OBSERVABILITY,
                ],
            ),
            stage("Hiring market", HIRING_MARKET_SKILLS),
        ],
    ),
]
