"""Deterministic, source-anchored semantic resume parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid5

from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSemantics,
    DatePrecision,
    SectionKind,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SemanticSourceAnchor,
)

SEMANTIC_SCHEMA_VERSION = "canonical-semantics/1.0.0"
SEMANTIC_PARSER_VERSION = "rezumi-semantic-parser/1.0.0"
_SEMANTIC_NAMESPACE = UUID("d6f8269c-f55b-4717-bdc7-2b552f564820")
_SOURCE_VALUE_TRIM = frozenset(" \t\r\n|-,;\u2013\u2014")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{6,}\d)(?!\w)")
# Hosts whose profile links are routinely written into a resume without a
# scheme ("github.com/alex", "de.linkedin.com/in/alex"). Bare hostnames are
# only read as links for these, so ordinary prose ("Node.js", "scikit-learn")
# is never swept up as a URL. Any subdomain of a listed host counts.
#
# The list is deliberately domain-wide rather than engineering-only: a resume
# is as likely to cite a Quant Stack Exchange profile, an SSRN paper, a Credly
# credential, a Behance portfolio, or a Substack as it is a GitHub account.
# Whether a link can then be *read* automatically is a separate question,
# answered by the connector registry - but a link that is never extracted here
# cannot even be stored, which is the failure this list exists to prevent.
_LINK_HOSTS = (
    # Professional networks and hiring
    "linkedin.com",
    "lnkd.in",
    "xing.com",
    "wellfound.com",
    "angel.co",
    "glassdoor.com",
    "indeed.com",
    "joinhandshake.com",
    "polywork.com",
    "read.cv",
    "contra.com",
    "about.me",
    # Code hosting and engineering
    "github.com",
    "github.io",
    "gitlab.com",
    "gitlab.io",
    "bitbucket.org",
    "codeberg.org",
    "sourceforge.net",
    "launchpad.net",
    "codepen.io",
    "replit.com",
    "glitch.com",
    "observablehq.com",
    "npmjs.com",
    "pypi.org",
    "crates.io",
    "rubygems.org",
    "packagist.org",
    "nuget.org",
    "hub.docker.com",
    "devpost.com",
    # Q&A and community reputation (finance, law, stats, academia, and more)
    "stackoverflow.com",
    "stackexchange.com",
    "serverfault.com",
    "superuser.com",
    "askubuntu.com",
    "mathoverflow.net",
    "stackapps.com",
    "quora.com",
    "reddit.com",
    # Competitive programming and data science
    "codeforces.com",
    "leetcode.com",
    "hackerrank.com",
    "hackerearth.com",
    "topcoder.com",
    "codechef.com",
    "kaggle.com",
    "numer.ai",
    "huggingface.co",
    "paperswithcode.com",
    "wandb.ai",
    "openml.org",
    # Research, academia, medicine, economics
    "orcid.org",
    "openalex.org",
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "ssrn.com",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "europepmc.org",
    "semanticscholar.org",
    "researchgate.net",
    "academia.edu",
    "scholar.google.com",
    "zenodo.org",
    "figshare.com",
    "osf.io",
    "dblp.org",
    "doi.org",
    "clinicaltrials.gov",
    "publons.com",
    "webofscience.com",
    "scopus.com",
    # Credentials, certification, and learning
    "credly.com",
    "youracclaim.com",
    "credential.net",
    "accredible.com",
    "badgr.com",
    "certmetrics.com",
    "coursera.org",
    "edx.org",
    "udacity.com",
    "udemy.com",
    "datacamp.com",
    "pluralsight.com",
    "learn.microsoft.com",
    "trailblazer.me",
    "cloudskillsboost.google",
    "pmi.org",
    "isc2.org",
    "scrum.org",
    # Design and creative
    "behance.net",
    "dribbble.com",
    "artstation.com",
    "deviantart.com",
    "500px.com",
    "unsplash.com",
    "figma.com",
    "myportfolio.com",
    "cargo.site",
    "vimeo.com",
    "layers.to",
    # Writing, publishing, and thought leadership
    "medium.com",
    "substack.com",
    "beehiiv.com",
    "hashnode.dev",
    "dev.to",
    "ghost.io",
    "wordpress.com",
    "blogger.com",
    "tumblr.com",
    "muckrack.com",
    "journoportfolio.com",
    "clippings.me",
    "contently.com",
    "authory.com",
    "goodreads.com",
    # Speaking and events
    "speakerdeck.com",
    "slideshare.net",
    "sessionize.com",
    "papercall.io",
    "ted.com",
    "meetup.com",
    # Regulated professional registers (finance, medicine, law)
    "brokercheck.finra.org",
    "adviserinfo.sec.gov",
    "sec.gov",
    "npiregistry.cms.hhs.gov",
    "doximity.com",
    "avvo.com",
    "martindale.com",
    "justia.com",
    "courtlistener.com",
    # Finance and markets
    "seekingalpha.com",
    "tradingview.com",
    "morningstar.com",
    "cfainstitute.org",
    # Site builders and personal-site hosts
    "notion.site",
    "super.site",
    "carrd.co",
    "webflow.io",
    "wixsite.com",
    "weebly.com",
    "strikingly.com",
    "squarespace.com",
    "framer.website",
    "netlify.app",
    "vercel.app",
    "pages.dev",
    "surge.sh",
    "herokuapp.com",
    "fly.dev",
    "onrender.com",
    "streamlit.app",
    "linktr.ee",
    "bio.link",
    # Social
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "threads.net",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "pinterest.com",
)
_URL = re.compile(
    r"(?:https?://|www\.)[^\s|\u2022\u00b7\t]+"
    r"|(?<![\w.@-])(?:[a-z0-9-]+\.)*(?:"
    + "|".join(host.replace(".", r"\.") for host in _LINK_HOSTS)
    + r")/[^\s|\u2022\u00b7\t]*",
    re.IGNORECASE,
)
# Sentence punctuation and wrapping brackets a resume puts around a link. Left
# on the value they break every downstream host/path match, so "(github.com/
# alex)." is read as an unsupported link instead of a GitHub profile.
_URL_TRAILING_PUNCTUATION = ".,;:!?*\u2018\u2019\u201c\u201d\"'"
_URL_CLOSING_BRACKETS = {")": "(", "]": "[", "}": "{", ">": "<"}
_DATE = re.compile(
    r"\b(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4}"
    r"|\d{1,2}[/-]\d{4}"
    r"|\d{4}[/-]\d{1,2}"
    r"|\d{4}"
    r"|Present|Current"
    r")\b",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"\s*(?:\||•|·|\t)\s*")
# Weak separators are only applied when a record still has unfilled names, so a
# header line is cut exactly as far as the record requires and no further. The
# first cut may use "at" ("Senior Engineer at Acme"); later cuts may not, so an
# institution such as "University of Texas at Austin" survives intact.
_WEAK_SPLIT_FIRST = re.compile(r"\s*,\s*|\s+[\u2013\u2014-]\s+|\s+at\s+", re.IGNORECASE)
_WEAK_SPLIT_REST = re.compile(r"\s*,\s*|\s+[\u2013\u2014-]\s+")
# Skills lists commonly separate individual skills with commas or semicolons in
# addition to pipes/bullets. Slashes and hyphens are intentionally excluded so
# compound skills like "CI/CD", "TCP/IP", or "A/B testing" stay intact.
_SKILL_SPLIT = re.compile(r"\s*(?:,|;|\||•|·)\s*")
_SUBSECTION_HEADINGS = frozenset(
    {
        "selected ai projects",
        "selected projects",
        "ai projects",
        "key projects",
        "personal projects",
        "certifications & achievements",
        "certifications and achievements",
    }
)
# Connector words that precede a date on a label-style line ("Issued Mar 2022,
# Expires Mar 2025"). Once the date itself is matched separately, the bare
# label word left over must not be treated as a real text-field value (e.g.
# misfilling a certification's credential_id with the word "Issued").
_DATE_LABEL_WORDS = frozenset(
    {"issued", "issue", "expires", "expire", "expiry", "valid", "from", "to", "through", "until"}
)


@dataclass(frozen=True, slots=True)
class _FieldCandidate:
    name: str
    field_type: SemanticFieldType
    value: str
    block: CanonicalBlock
    start: int
    end: int
    confidence_basis_points: int
    date_precision: DatePrecision | None = None


class LocalResumeParserProvider:
    """Local baseline parser with deterministic IDs and no provider credentials."""

    async def parse(
        self,
        document_id: UUID,
        resume: CanonicalResume,
        source_sha256: str,
    ) -> CanonicalSemantics:
        if len(source_sha256) != 64:
            raise ValueError("semantic parsing requires the source document SHA-256")
        entities: list[SemanticEntity] = []
        for section_index, section in enumerate(resume.sections):
            kind = _entity_kind(section.kind)
            if kind is None and section_index == 0 and section.kind is SectionKind.OTHER:
                kind = SemanticEntityKind.CONTACT
            if kind is None:
                continue
            if kind is SemanticEntityKind.CONTACT:
                candidates = _contact_candidates(section.blocks)
                if candidates:
                    entities.append(
                        _entity(document_id, kind, section.id, 0, candidates, source_sha256)
                    )
                continue
            groups = _entity_block_groups(kind, section.blocks)
            for index, blocks in enumerate(groups):
                candidates = _group_candidates(kind, blocks)
                if candidates:
                    entities.append(
                        _entity(
                            document_id,
                            kind,
                            section.id,
                            index,
                            candidates,
                            source_sha256,
                        )
                    )
        warnings: list[str] = []
        discovered = {entity.kind for entity in entities}
        if SemanticEntityKind.CONTACT not in discovered:
            warnings.append("semantic_contact_not_detected")
        if SemanticEntityKind.EXPERIENCE not in discovered:
            warnings.append("semantic_experience_not_detected")
        return CanonicalSemantics(
            schema_version=SEMANTIC_SCHEMA_VERSION,
            parser_version=SEMANTIC_PARSER_VERSION,
            entities=tuple(entities),
            warnings=tuple(warnings),
        )


def _url_spans(text: str) -> tuple[tuple[str, int, int], ...]:
    """Return each link in ``text`` with its exact, punctuation-free offsets.

    Offsets stay exact because they anchor the field back to the source
    document, so trailing punctuation is dropped by shortening the span rather
    than by rewriting the value.
    """

    spans: list[tuple[str, int, int]] = []
    for match in _URL.finditer(text):
        start, end = match.start(), match.end()
        while end > start:
            last = text[end - 1]
            opener = _URL_CLOSING_BRACKETS.get(last)
            if opener is not None:
                value = text[start:end]
                if value.count(opener) >= value.count(last):
                    break
                end -= 1
                continue
            if last in _URL_TRAILING_PUNCTUATION:
                end -= 1
                continue
            break
        if end - start >= 4:
            spans.append((text[start:end], start, end))
    return tuple(spans)


def _overlaps(start: int, end: int, spans: tuple[tuple[str, int, int], ...]) -> bool:
    return any(start < span_end and span_start < end for _, span_start, span_end in spans)


def _link_names(kind: SemanticEntityKind) -> tuple[str, ...]:
    """Record kinds that carry an external link of their own."""

    if kind in {
        SemanticEntityKind.EXPERIENCE,
        SemanticEntityKind.EDUCATION,
        SemanticEntityKind.PROJECT,
        SemanticEntityKind.CERTIFICATION,
    }:
        return ("link",)
    return ()


def _entity_kind(section_kind: SectionKind) -> SemanticEntityKind | None:
    return {
        SectionKind.CONTACT: SemanticEntityKind.CONTACT,
        SectionKind.EXPERIENCE: SemanticEntityKind.EXPERIENCE,
        SectionKind.EDUCATION: SemanticEntityKind.EDUCATION,
        SectionKind.PROJECTS: SemanticEntityKind.PROJECT,
        SectionKind.SKILLS: SemanticEntityKind.SKILL,
        SectionKind.CERTIFICATIONS: SemanticEntityKind.CERTIFICATION,
    }.get(section_kind)


def _contact_candidates(blocks: tuple[CanonicalBlock, ...]) -> tuple[_FieldCandidate, ...]:
    candidates: list[_FieldCandidate] = []
    name_added = False
    for block in blocks:
        url_spans = _url_spans(block.text)
        for pattern, name, field_type in (
            (_EMAIL, "email", SemanticFieldType.EMAIL),
            (_PHONE, "phone", SemanticFieldType.PHONE),
        ):
            for match in pattern.finditer(block.text):
                if _overlaps(match.start(), match.end(), url_spans):
                    continue
                candidates.append(
                    _FieldCandidate(
                        name,
                        field_type,
                        match.group().strip(),
                        block,
                        match.start(),
                        match.end(),
                        9_500,
                    )
                )
        for value, start, end in url_spans:
            candidates.append(
                _FieldCandidate(
                    "link",
                    SemanticFieldType.URL,
                    value,
                    block,
                    start,
                    end,
                    9_500,
                )
            )
        if (
            not name_added
            and block.kind is not BlockKind.BULLET
            and not url_spans
            and not any(pattern.search(block.text) for pattern in (_EMAIL, _PHONE))
            and 1 < len(block.text.split()) <= 6
        ):
            candidates.append(
                _FieldCandidate(
                    "name",
                    SemanticFieldType.TEXT,
                    block.text,
                    block,
                    0,
                    len(block.text),
                    7_500,
                )
            )
            name_added = True
    return tuple(candidates)


def _group_candidates(
    kind: SemanticEntityKind,
    blocks: tuple[CanonicalBlock, ...],
) -> tuple[_FieldCandidate, ...]:
    if kind is SemanticEntityKind.SKILL:
        skill_candidates: list[_FieldCandidate] = []
        for block in blocks:
            text = block.text
            prefix_len = 0
            if ":" in text:
                prefix, _, text = text.partition(":")
                prefix_len = len(prefix) + 1
            skill_candidates.extend(
                _FieldCandidate(
                    "name",
                    SemanticFieldType.TEXT,
                    value,
                    block,
                    start + prefix_len,
                    end + prefix_len,
                    8_000,
                )
                for value, start, end in _source_values(text, (), _SKILL_SPLIT)
            )
        return tuple(skill_candidates)

    candidates: list[_FieldCandidate] = []
    pending_text: list[str] = []
    pending_dates = list(_date_names(kind))
    pending_links = list(_link_names(kind))
    for index, block in enumerate(blocks):
        if not pending_text:
            pending_text = list(_text_names_for_block(kind, block))
        if block.kind is BlockKind.BULLET:
            name = "achievement" if kind is SemanticEntityKind.EXPERIENCE else "description"
            candidates.append(
                _FieldCandidate(
                    name,
                    SemanticFieldType.BULLET,
                    block.text,
                    block,
                    0,
                    len(block.text),
                    8_500,
                )
            )
            continue
        if _is_wrapped_bullet_continuation(block, blocks, index):
            if kind is SemanticEntityKind.EXPERIENCE:
                candidates.append(
                    _FieldCandidate(
                        "achievement",
                        SemanticFieldType.BULLET,
                        block.text,
                        block,
                        0,
                        len(block.text),
                        8_000,
                    )
                )
            continue
        candidates.extend(_header_candidates(block, pending_text, pending_dates, pending_links))

    if candidates:
        return tuple(candidates)
    header = next(
        (block for block in blocks if block.kind is not BlockKind.BULLET and block.text),
        None,
    )
    if header is None:
        return ()
    # A header whose only content is separator punctuation yields no exact
    # source value. Name the whole line rather than dropping the record.
    return (
        _FieldCandidate(
            _text_names_for_block(kind, header)[0],
            SemanticFieldType.TEXT,
            header.text,
            header,
            0,
            len(header.text),
            5_500,
        ),
    )


def _header_candidates(
    block: CanonicalBlock,
    pending_text: list[str],
    pending_dates: list[str],
    pending_links: list[str],
) -> list[_FieldCandidate]:
    """Consume the record's still-unfilled names from one header line."""
    text = block.text
    candidates: list[_FieldCandidate] = []
    # Links are claimed before anything else, so a project or credential URL
    # lands in a field of its own instead of being cut up as an employer or a
    # location, and so a year inside a path ("/2024/report") is not read as the
    # record's date.
    url_spans = _url_spans(text)
    for value, start, end in url_spans:
        if not pending_links:
            break
        candidates.append(
            _FieldCandidate(
                pending_links.pop(0),
                SemanticFieldType.URL,
                value,
                block,
                start,
                end,
                9_000,
            )
        )
    date_matches = [
        match
        for match in _DATE.finditer(text)
        if not _overlaps(match.start(), match.end(), url_spans)
    ]
    for match in date_matches:
        if not pending_dates:
            break
        candidates.append(
            _FieldCandidate(
                pending_dates.pop(0),
                SemanticFieldType.DATE,
                match.group(),
                block,
                match.start(),
                match.end(),
                8_500,
                _date_precision(match.group()),
            )
        )
    segments = _source_values(
        text,
        tuple(
            sorted(
                [(match.start(), match.end()) for match in date_matches]
                + [(start, end) for _, start, end in url_spans]
            )
        ),
    )
    for value, start, end in _split_for_names(text, segments, len(pending_text)):
        if not pending_text:
            break
        if date_matches and value.strip().casefold() in _DATE_LABEL_WORDS:
            continue
        candidates.append(
            _FieldCandidate(
                pending_text.pop(0),
                SemanticFieldType.TEXT,
                value,
                block,
                start,
                end,
                7_000,
            )
        )
    return candidates


def _split_for_names(
    text: str,
    segments: tuple[tuple[str, int, int], ...],
    needed: int,
) -> tuple[tuple[str, int, int], ...]:
    """Sub-split header segments only while the record still needs more names.

    "Senior Engineer, Acme Corp" has to become a title and an employer, but
    "San Francisco, CA" has to stay a single location once title and employer
    are already filled. Splitting strictly on demand keeps both readings exact.
    """
    if len(segments) >= needed:
        return segments
    expanded: list[tuple[str, int, int]] = []
    for index, (_, start, end) in enumerate(segments):
        room = needed - len(expanded) - (len(segments) - index - 1)
        expanded.extend(_split_segment(text, start, end, room))
    return tuple(expanded)


def _split_segment(
    text: str,
    start: int,
    end: int,
    limit: int,
) -> tuple[tuple[str, int, int], ...]:
    """Cut one header segment into at most ``limit`` exact source values."""
    parts: list[tuple[str, int, int]] = [(text[start:end], start, end)]
    pattern = _WEAK_SPLIT_FIRST
    while len(parts) < limit:
        value, value_start, value_end = parts[-1]
        cut = _source_values(value, (), pattern)
        if len(cut) < 2:
            break
        head, head_start, head_end = cut[0]
        rest_start = value_start + cut[1][1]
        parts[-1] = (head, value_start + head_start, value_start + head_end)
        parts.append((text[rest_start:value_end], rest_start, value_end))
        pattern = _WEAK_SPLIT_REST
    return tuple(parts)


def _entity_block_groups(
    kind: SemanticEntityKind,
    blocks: tuple[CanonicalBlock, ...],
) -> tuple[tuple[CanonicalBlock, ...], ...]:
    if kind is SemanticEntityKind.EDUCATION:
        blocks = _education_blocks(blocks)
    if kind is SemanticEntityKind.SKILL:
        # Every skill line belongs to one structured Skills entity, so the review
        # UI shows a single section listing each skill instead of one card per
        # line. An empty section yields no group and is skipped by the caller.
        return (blocks,) if blocks else ()
    groups: list[list[CanonicalBlock]] = []
    for block in blocks:
        if block.kind is BlockKind.BULLET:
            if groups:
                groups[-1].append(block)
            else:
                groups.append([block])
            continue
        starts_record = not groups or _starts_new_record(kind, block, groups[-1])
        if starts_record:
            groups.append([block])
        else:
            groups[-1].append(block)
    return tuple(tuple(group) for group in groups)


def _starts_new_record(
    kind: SemanticEntityKind,
    block: CanonicalBlock,
    current_group: list[CanonicalBlock],
) -> bool:
    if _carries_date(current_group) and _DATE.search(block.text) is not None:
        return True
    if not any(item.kind is BlockKind.BULLET for item in current_group):
        return False
    text = block.text.lstrip()
    if text and text[0].islower():
        return False
    if "|" in block.text:
        return True
    if _looks_like_subsection_heading(block.text):
        return True
    return "," in block.text and _DATE.search(block.text) is None


def _looks_like_subsection_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 64 or _DATE.search(stripped):
        return False
    normalized = re.sub(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$", "", stripped).strip().casefold()
    if normalized in _SUBSECTION_HEADINGS:
        return True
    words = stripped.split()
    return len(words) <= 8 and stripped.isupper()


def _is_wrapped_bullet_continuation(
    block: CanonicalBlock,
    blocks: tuple[CanonicalBlock, ...],
    index: int,
) -> bool:
    if block.kind is BlockKind.BULLET or index == 0:
        return False
    if blocks[index - 1].kind is BlockKind.BULLET:
        return True
    text = block.text.lstrip()
    return bool(text) and text[0].islower()


def _education_blocks(blocks: tuple[CanonicalBlock, ...]) -> tuple[CanonicalBlock, ...]:
    cutoff = len(blocks)
    for index, block in enumerate(blocks):
        if block.kind is not BlockKind.HEADING:
            continue
        normalized = block.text.casefold()
        if "certification" in normalized or "achievement" in normalized:
            cutoff = index
            break
    return blocks[:cutoff]


def _text_names_for_block(kind: SemanticEntityKind, block: CanonicalBlock) -> tuple[str, ...]:
    if kind is SemanticEntityKind.EXPERIENCE:
        if "|" in block.text:
            return ("employer", "title", "location")
        return ("title", "employer", "location")
    if kind is SemanticEntityKind.EDUCATION:
        if "|" in block.text:
            return ("institution", "degree", "field", "location")
        return ("degree", "institution", "field", "location")
    return _text_names(kind)


def _carries_date(group: list[CanonicalBlock]) -> bool:
    """Whether a record's header lines already supplied a date range."""
    return any(
        block.kind is not BlockKind.BULLET and _DATE.search(block.text) is not None
        for block in group
    )


def _text_names(kind: SemanticEntityKind) -> tuple[str, ...]:
    return {
        SemanticEntityKind.EXPERIENCE: ("title", "employer", "location"),
        SemanticEntityKind.EDUCATION: ("degree", "institution", "field", "location"),
        SemanticEntityKind.PROJECT: ("name", "description"),
        SemanticEntityKind.CERTIFICATION: ("name", "issuer", "credential_id"),
        SemanticEntityKind.CONTACT: ("name",),
        SemanticEntityKind.SKILL: ("name",),
    }[kind]


def _date_names(kind: SemanticEntityKind) -> tuple[str, ...]:
    if kind is SemanticEntityKind.CERTIFICATION:
        return ("issued_date", "expires_date")
    if kind in {
        SemanticEntityKind.EXPERIENCE,
        SemanticEntityKind.EDUCATION,
        SemanticEntityKind.PROJECT,
    }:
        return ("start_date", "end_date")
    return ()


def _date_precision(value: str) -> DatePrecision:
    if re.search(r"[A-Za-z]", value) and value.casefold() not in {"present", "current"}:
        return DatePrecision.MONTH
    if re.fullmatch(r"(?:\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2})", value):
        return DatePrecision.MONTH
    if re.fullmatch(r"\d{4}", value):
        return DatePrecision.YEAR
    return DatePrecision.UNKNOWN


def _source_values(
    text: str,
    excluded_ranges: tuple[tuple[int, int], ...],
    splitter: re.Pattern[str] = _SPLIT,
) -> tuple[tuple[str, int, int], ...]:
    """Return only contiguous source substrings with their exact block offsets."""
    values: list[tuple[str, int, int]] = []
    source_ranges: list[tuple[int, int]] = []
    cursor = 0
    for start, end in excluded_ranges:
        if cursor < start:
            source_ranges.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < len(text):
        source_ranges.append((cursor, len(text)))

    for source_start, source_end in source_ranges:
        segment_start = source_start
        for separator in splitter.finditer(text, source_start, source_end):
            _append_source_value(values, text, segment_start, separator.start())
            segment_start = separator.end()
        _append_source_value(values, text, segment_start, source_end)
    return tuple(values)


def _append_source_value(
    values: list[tuple[str, int, int]],
    text: str,
    start: int,
    end: int,
) -> None:
    while start < end and text[start] in _SOURCE_VALUE_TRIM:
        start += 1
    while end > start and text[end - 1] in _SOURCE_VALUE_TRIM:
        end -= 1
    if start == end or text[start:end].casefold() == "to":
        return
    values.append((text[start:end], start, end))


def _entity(
    document_id: UUID,
    kind: SemanticEntityKind,
    section_id: UUID,
    entity_index: int,
    candidates: tuple[_FieldCandidate, ...],
    source_sha256: str,
) -> SemanticEntity:
    entity_id = uuid5(
        _SEMANTIC_NAMESPACE,
        f"{document_id}:{section_id}:{kind.value}:{entity_index}",
    )
    fields = tuple(
        _field(entity_id, index, candidate, source_sha256)
        for index, candidate in enumerate(candidates)
    )
    return SemanticEntity(
        id=entity_id,
        kind=kind,
        review_state=SemanticReviewState.UNREVIEWED,
        fields=fields,
        source_section_id=section_id,
    )


def _field(
    entity_id: UUID,
    index: int,
    candidate: _FieldCandidate,
    source_sha256: str,
) -> SemanticField:
    span = candidate.block.spans[0] if candidate.block.spans else None
    if span is None:
        raise ValueError("semantic source fields require an extracted source span")
    field_id = uuid5(
        _SEMANTIC_NAMESPACE,
        f"{entity_id}:{candidate.name}:{index}:{sha256(candidate.value.encode()).hexdigest()}",
    )
    return SemanticField(
        id=field_id,
        name=candidate.name,
        field_type=candidate.field_type,
        value=candidate.value,
        confidence_basis_points=candidate.confidence_basis_points,
        review_state=SemanticReviewState.UNREVIEWED,
        anchors=(
            SemanticSourceAnchor(
                block_id=candidate.block.id,
                page=span.page,
                start=span.start + candidate.start,
                end=span.start + candidate.end,
                source_sha256=source_sha256,
            ),
        ),
        date_precision=candidate.date_precision,
    )
