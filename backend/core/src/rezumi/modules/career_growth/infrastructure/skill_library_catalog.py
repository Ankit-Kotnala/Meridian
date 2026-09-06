"""Curated third-party learning links and self-authored readable notes.

Course URLs point at public platform pages. Notes are original study articles,
never copies of a paid curriculum. Completion is not Career Record evidence.
"""

from __future__ import annotations

from urllib.parse import urlparse

from rezumi.modules.career_growth.application.role_roadmap_ports import (
    SkillLibrary,
    SkillLibraryNote,
    SkillLibraryResource,
)
from rezumi.modules.career_growth.domain.errors import CareerGrowthValidationError
from rezumi.modules.career_growth.infrastructure.skill_library_extras import (
    family_bonus,
    keyword_bonus,
    skill_discovery,
)
from rezumi.modules.career_growth.infrastructure.skill_library_notes import study_articles
from rezumi.modules.career_growth.infrastructure.skill_library_packs import (
    PACKS,
    extra_for_skill,
    family_for_skill,
    search_free,
    search_paid,
)

SKILL_LIBRARY_VERSION = "skill-libraries/2026-09-06.3"

_NOTE_CONTENT_MAX = 50_000
_FREE_CAP = 40
_PAID_CAP = 20

_ALLOWED_ROOTS = frozenset(
    {
        "a11yproject.com",
        "agilealliance.org",
        "amplitude.com",
        "apple.com",
        "asq.org",
        "atlassian.com",
        "attack.mitre.org",
        "aws.amazon.com",
        "brown.edu",
        "cheatsheetseries.owasp.org",
        "cloud.google.com",
        "cloudflare.com",
        "cncf.io",
        "coursera.org",
        "cwe.mitre.org",
        "deeplearning.ai",
        "developer.android.com",
        "developer.apple.com",
        "developer.hashicorp.com",
        "developer.mozilla.org",
        "developers.google.com",
        "docs.aws.amazon.com",
        "docs.docker.com",
        "docs.github.com",
        "docs.pytest.org",
        "docs.python.org",
        "dol.gov",
        "edx.org",
        "eeoc.gov",
        "facebookblueprint.com",
        "fast.ai",
        "figma.com",
        "freecodecamp.org",
        "fullstackopen.com",
        "git-scm.com",
        "github.com",
        "gong.io",
        "gov.uk",
        "grafana.com",
        "grow.google",
        "harvard.edu",
        "hbr.org",
        "help.figma.com",
        "hubspot.com",
        "huggingface.co",
        "iiba.org",
        "ifrs.org",
        "interaction-design.org",
        "investopedia.com",
        "investor.gov",
        "javascript.info",
        "jestjs.io",
        "kaggle.com",
        "kafka.apache.org",
        "khanacademy.org",
        "kubernetes.io",
        "learn.microsoft.com",
        "leetcode.com",
        "linkedin.com",
        "m3.material.io",
        "material.io",
        "man7.org",
        "manager-tools.com",
        "ministryoftesting.com",
        "mit.edu",
        "mitre.org",
        "mixpanel.com",
        "moz.com",
        "nngroup.com",
        "neetcode.io",
        "nextjs.org",
        "nodejs.org",
        "numpy.org",
        "ocw.mit.edu",
        "owasp.org",
        "pandas.pydata.org",
        "pdos.csail.mit.edu",
        "playwright.dev",
        "pmi.org",
        "prometheus.io",
        "python.org",
        "portswigger.net",
        "postgresql.org",
        "pytorch.org",
        "rabbitmq.com",
        "react.dev",
        "redis.io",
        "reforge.com",
        "rework.withgoogle.com",
        "rfc-editor.org",
        "salesforce.com",
        "scikit-learn.org",
        "scrum.org",
        "shrm.org",
        "skills.github.com",
        "skillshop.withgoogle.com",
        "skillbuilder.aws",
        "sre.google",
        "svpg.com",
        "tensorflow.org",
        "keras.io",
        "angular.dev",
        "vuejs.org",
        "cloudskillsboost.google",
        "testing-library.com",
        "thegooddocsproject.dev",
        "theodinproject.com",
        "thoughtworks.com",
        "trailhead.salesforce.com",
        "typescriptlang.org",
        "ubuntu.com",
        "udacity.com",
        "udemy.com",
        "use-the-index-luke.com",
        "visualgo.net",
        "w3.org",
        "web.dev",
        "webaim.org",
        "withgoogle.com",
        "youtube.com",
        "youtu.be",
    }
)


def library_for_skill(
    name: str,
    *,
    why: str = "",
    how_to_start: str = "",
) -> SkillLibrary:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise CareerGrowthValidationError("skill name is required")
    family = family_for_skill(cleaned)
    pack = PACKS.get(family, PACKS["product"])
    extra_free, extra_paid = extra_for_skill(cleaned)
    bonus_free, bonus_paid = family_bonus(family)
    keyword_free, keyword_paid = keyword_bonus(cleaned)
    discover_free, discover_paid = skill_discovery(cleaned)
    free = _resources(
        _dedupe(
            (
                *pack.get("free", ()),
                *bonus_free,
                *extra_free,
                *keyword_free,
                *search_free(cleaned),
                *discover_free,
            )
        ),
        default_kind="youtube",
        cap=_FREE_CAP,
    )
    paid = _resources(
        _dedupe(
            (
                *pack.get("paid", ()),
                *bonus_paid,
                *extra_paid,
                *keyword_paid,
                *search_paid(cleaned),
                *discover_paid,
            )
        ),
        default_kind="coursera",
        cap=_PAID_CAP,
    )
    notes = tuple(
        _article_note(title, body, slug=_file_slug(cleaned), index=index)
        for index, (title, body) in enumerate(
            study_articles(cleaned, how_to_start=how_to_start, why=why),
            start=1,
        )
    )
    return SkillLibrary(free_courses=free, notes=notes, paid_courses=paid)


def library_document(library: SkillLibrary) -> dict[str, object]:
    return {
        "freeCourses": [_resource_document(item) for item in library.free_courses],
        "notes": [_note_document(item) for item in library.notes],
        "paidCourses": [_resource_document(item) for item in library.paid_courses],
        "version": SKILL_LIBRARY_VERSION,
    }


def library_from_document(value: object, *, name: str, why: str, how_to_start: str) -> SkillLibrary:
    if not isinstance(value, dict):
        return library_for_skill(name, why=why, how_to_start=how_to_start)
    generated = library_for_skill(name, why=why, how_to_start=how_to_start)
    stored_version = str(value.get("version") or "")
    free = _resources_from_document(value.get("freeCourses"))
    paid = _resources_from_document(value.get("paidCourses"))
    notes = _notes_from_document(value.get("notes"))
    stale = (
        stored_version != SKILL_LIBRARY_VERSION
        or len(free) < 20
        or len(paid) < 12
        or len(notes) < 3
        or any(item.file_name.endswith(".md") for item in notes)
        or any(len(item.content) < 1200 for item in notes)
    )
    if stale:
        return generated
    return SkillLibrary(free_courses=free, notes=notes, paid_courses=paid)


def _dedupe(entries: tuple[tuple[str, str, str], ...]) -> tuple[tuple[str, str, str], ...]:
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for title, provider, url in entries:
        key = url.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append((title, provider, url))
    return tuple(out)


def _resources(
    entries: tuple[tuple[str, str, str], ...],
    *,
    default_kind: str,
    cap: int,
) -> tuple[SkillLibraryResource, ...]:
    resources = []
    for title, provider, url in entries:
        try:
            resources.append(
                SkillLibraryResource(
                    kind=_kind_for_url(url, default=default_kind),
                    provider=_text(provider, "resource provider", 80),
                    title=_text(title, "resource title", 200),
                    url=_https_url(url),
                )
            )
        except CareerGrowthValidationError:
            continue
        if len(resources) >= cap:
            break
    return tuple(resources)


def _article_note(title: str, body: str, *, slug: str, index: int) -> SkillLibraryNote:
    suffixes = {1: "concepts", 2: "practice", 3: "field-notes"}
    suffix = suffixes.get(index, f"part-{index}")
    return SkillLibraryNote(
        content=_text(body, "note content", _NOTE_CONTENT_MAX),
        file_name=f"{slug}-{suffix}.pdf",
        format="article",
        title=_text(title, "note title", 200),
    )


def _resources_from_document(value: object) -> tuple[SkillLibraryResource, ...]:
    if not isinstance(value, list):
        return ()
    resources: list[SkillLibraryResource] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        provider = str(item.get("provider") or "")
        url = str(item.get("url") or "")
        kind = str(item.get("kind") or "other")
        if not title or not provider or not url:
            continue
        try:
            resources.append(
                SkillLibraryResource(
                    kind=_text(kind, "resource kind", 40),
                    provider=_text(provider, "resource provider", 80),
                    title=_text(title, "resource title", 200),
                    url=_https_url(url),
                )
            )
        except CareerGrowthValidationError:
            continue
    return tuple(resources)


def _notes_from_document(value: object) -> tuple[SkillLibraryNote, ...]:
    if not isinstance(value, list):
        return ()
    notes: list[SkillLibraryNote] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        content = str(item.get("content") or "")
        file_name = str(item.get("fileName") or "")
        fmt = str(item.get("format") or "article")
        if not title or not content:
            continue
        try:
            notes.append(
                SkillLibraryNote(
                    content=_text(content, "note content", _NOTE_CONTENT_MAX),
                    file_name=_text(
                        file_name or f"{_file_slug(title)}.pdf",
                        "note file name",
                        120,
                    ),
                    format=_text(fmt, "note format", 40),
                    title=_text(title, "note title", 200),
                )
            )
        except CareerGrowthValidationError:
            continue
    return tuple(notes)


def _resource_document(item: SkillLibraryResource) -> dict[str, str]:
    return {
        "kind": item.kind,
        "provider": item.provider,
        "title": item.title,
        "url": item.url,
    }


def _note_document(item: SkillLibraryNote) -> dict[str, str]:
    return {
        "content": item.content,
        "fileName": item.file_name,
        "format": item.format,
        "title": item.title,
    }


def _kind_for_url(url: str, *, default: str) -> str:
    host = _normalized_host(urlparse(url).hostname or "")
    if host in {"youtube.com", "youtu.be"}:
        return "youtube"
    if host == "coursera.org":
        return "coursera"
    if host == "udemy.com":
        return "udemy"
    if host == "edx.org":
        return "edx"
    if host == "khanacademy.org":
        return "khan_academy"
    if host in {"ocw.mit.edu", "mit.edu"} or host.endswith(".mit.edu"):
        return "lecture_notes"
    if host in {"cs50.harvard.edu", "harvard.edu"} or host.endswith(".harvard.edu"):
        return "lecture_notes"
    if default == "youtube":
        return "docs" if host not in {"youtube.com", "youtu.be"} else "youtube"
    return default


def _https_url(value: str) -> str:
    parsed = urlparse(value.strip())
    host = _normalized_host(parsed.hostname or "")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or not _host_allowed(host)
    ):
        raise CareerGrowthValidationError("skill library URL must be an allowlisted HTTPS page")
    return parsed.geturl()


def _host_allowed(host: str) -> bool:
    if host in _ALLOWED_ROOTS:
        return True
    return any(host.endswith(f".{root}") for root in _ALLOWED_ROOTS)


def _normalized_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def _text(value: str, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not 1 <= len(normalized) <= maximum:
        raise CareerGrowthValidationError(
            f"{field} must contain between 1 and {maximum} characters"
        )
    if "\x00" in normalized:
        raise CareerGrowthValidationError(f"{field} contains unsupported characters")
    return normalized


def _file_slug(value: str) -> str:
    chars = [character.lower() if character.isalnum() else "-" for character in value.strip()]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80] or "skill"
