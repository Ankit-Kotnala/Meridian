"""Self-authored role roadmaps used by the Mongo seed.

These documents are original teaching paths, not copies of a third-party
roadmap site. Job listings are not stored here — live catalog jobs come from
authorized employer boards.
"""

from __future__ import annotations

from typing import Any

from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.business import (
    BUSINESS_ROLES,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.data_ai import (
    DATA_AI_ROLES,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.engineering import (
    ENGINEERING_ROLES,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.go_to_market import (
    GO_TO_MARKET_ROLES,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.operations import (
    OPERATIONS_ROLES,
)
from rezumi.modules.career_growth.infrastructure.role_roadmap_catalog.product_design import (
    PRODUCT_DESIGN_ROLES,
)

ROLE_ROADMAPS: list[dict[str, Any]] = [
    *ENGINEERING_ROLES,
    *DATA_AI_ROLES,
    *PRODUCT_DESIGN_ROLES,
    *GO_TO_MARKET_ROLES,
    *BUSINESS_ROLES,
    *OPERATIONS_ROLES,
]
