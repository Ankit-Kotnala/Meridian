"""Application-boundary adapter from Job Match to Change Studio grounding."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from rezumi.modules.change_studio.application import (
    JobMatchAnalysisContext,
    RequirementMatchContext,
)
from rezumi.modules.change_studio.domain import (
    ChangeStudioNotFound,
    RequirementGroundingContext,
)
from rezumi.modules.job_match.application import JobMatchNotFound, JobMatchService


class JobMatchChangeStudioAnalysisProvider:
    """Consume only the Job Match application view, never its persistence tables."""

    def __init__(self, service: JobMatchService) -> None:
        self._service = service

    async def analysis(self, owner_user_id: UUID, analysis_id: UUID) -> JobMatchAnalysisContext:
        try:
            view = await self._service.get_analysis(owner_user_id, analysis_id)
        except JobMatchNotFound as exc:
            raise ChangeStudioNotFound from exc
        links_by_match: defaultdict[UUID, list[UUID]] = defaultdict(list)
        for link in view.evidence_links:
            links_by_match[link.requirement_match_id].append(link.evidence_id)
        return JobMatchAnalysisContext(
            job_id=view.job.id,
            job_title=view.job.title,
            analysis_id=view.analysis.id,
            display_score=view.analysis.display_score,
            requirements=tuple(
                RequirementMatchContext(
                    requirement=RequirementGroundingContext(
                        id=match.requirement_id,
                        text=match.requirement_text,
                        requirement_type=match.requirement_type.value,
                        importance=match.importance.value,
                    ),
                    match_state=match.match_state.value,
                    hard_gap=match.hard_gap,
                    evidence_ids=tuple(dict.fromkeys(links_by_match[match.id])),
                )
                for match in sorted(
                    view.requirement_matches,
                    key=lambda item: (item.hard_gap, item.score_basis_points, str(item.id)),
                )
            ),
        )
