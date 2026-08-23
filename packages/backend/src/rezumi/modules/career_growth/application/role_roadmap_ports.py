"""Read-only port for curated, versioned role-roadmap guidance (Phase 13).

Content behind this port is self-authored and versioned (see
`rezumi.development.seed_role_roadmaps`), never live-scraped — this repo's own
governance (ADR 0019 §5) and third-party roadmap-site licenses (checked before
this feature was built) both rule out reproducing another site's roadmap
content. This composes with the existing gap bridge
(`create_development_item_from_gap`); no new bounded context is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RoadmapSkillGuidance:
    role_slug: str
    stage: str
    skill_name: str
    why: str
    how_to_start: str


class RoleRoadmapProvider(Protocol):
    async def find_skill_guidance(self, skill_label: str) -> RoadmapSkillGuidance | None: ...
