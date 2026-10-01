"""Which declared-link platforms may be read automatically, and by whom.

Resumes are not only written by engineers. A finance analyst cites a Quant
Stack Exchange profile and an SSRN paper, a clinician cites PubMed and a
medical society register, a consultant cites Speaker Deck and a Substack, a
designer cites Behance. Every one of those links belongs in the career record;
they differ only in whether Rezumi may *read* them automatically.

Three outcomes, and every recognized host resolves to exactly one:

- a dedicated API connector, when the platform documents a public, key-free
  read of profile data (`API_PLATFORM_DOMAINS`);
- the generic HTML portfolio fallback, for server-rendered public pages
  (anything not listed here);
- a refusal carrying the reason (`BLOCKED_PLATFORMS`), when terms of service,
  robots.txt, or a client-rendered/consent-walled page mean an automated read
  would be either impermissible or worthless. A refusal is deliberate: the
  declared link is still stored as evidence, and the user adds the achievement
  by hand rather than receiving scraped navigation chrome as "achievements".

Kept in its own module so both the connector registry and the portfolio
fallback consult the same lists without importing each other. Every entry is
matched by domain *suffix*: a regional, mobile, or vanity subdomain
(`de.linkedin.com`, `m.facebook.com`, `gist.github.com`) is the same platform
as its apex domain, and an exact-match check silently routes those to the
wrong connector.
"""

from __future__ import annotations

from rezumi.modules.career_record.application.declared_profile_ports import (
    host_matches,
    hostname,
)

_MANUAL_ENTRY_HINT = "Add the achievement manually - the link stays on your record as evidence."
_AUTOMATION_FORBIDDEN = "{platform} does not permit automated profile reads. " + _MANUAL_ENTRY_HINT
_NO_PUBLIC_API = (
    "{platform} does not expose a public profile API Rezumi may read. " + _MANUAL_ENTRY_HINT
)
_CLIENT_RENDERED = (
    "{platform} builds its pages in the browser, so there is nothing readable to "
    "import from the link. " + _MANUAL_ENTRY_HINT
)
_PUBLIC_REGISTER = (
    "{platform} is a public register rather than a machine-readable profile "
    "source. " + _MANUAL_ENTRY_HINT
)
_LINKEDIN_AUTHORIZED_ONLY = (
    "LinkedIn public profile links cannot be read anonymously. LinkedIn's official profile API "
    "requires an approved application and the member's access token; " + _MANUAL_ENTRY_HINT
)


def _forbidden(*domains: str, platform: str) -> tuple[tuple[str, str], ...]:
    return tuple((domain, _AUTOMATION_FORBIDDEN.format(platform=platform)) for domain in domains)


def _no_api(*domains: str, platform: str) -> tuple[tuple[str, str], ...]:
    return tuple((domain, _NO_PUBLIC_API.format(platform=platform)) for domain in domains)


def _client_rendered(*domains: str, platform: str) -> tuple[tuple[str, str], ...]:
    return tuple((domain, _CLIENT_RENDERED.format(platform=platform)) for domain in domains)


def _register(*domains: str, platform: str) -> tuple[tuple[str, str], ...]:
    return tuple((domain, _PUBLIC_REGISTER.format(platform=platform)) for domain in domains)


def _authorized_only(*domains: str, reason: str) -> tuple[tuple[str, str], ...]:
    return tuple((domain, reason) for domain in domains)


# Platforms excluded for cause. Blocking is enforced here rather than left to
# documentation, because the portfolio fallback would otherwise happily scrape
# every one of them and present the result as the user's achievements. See
# `registry.py` for the per-platform findings behind the engineering entries.
BLOCKED_PLATFORMS: tuple[tuple[str, str], ...] = (
    # --- Professional networks -------------------------------------------
    *_authorized_only("linkedin.com", "lnkd.in", reason=_LINKEDIN_AUTHORIZED_ONLY),
    *_forbidden("xing.com", platform="XING"),
    *_forbidden("wellfound.com", "angel.co", platform="Wellfound"),
    *_forbidden("glassdoor.com", "glassdoor.co.in", platform="Glassdoor"),
    *_forbidden("indeed.com", platform="Indeed"),
    *_forbidden("joinhandshake.com", platform="Handshake"),
    # --- Social ------------------------------------------------------------
    *_forbidden("facebook.com", "fb.com", platform="Facebook"),
    *_forbidden("instagram.com", platform="Instagram"),
    *_forbidden("threads.net", "threads.com", platform="Threads"),
    *_forbidden("tiktok.com", platform="TikTok"),
    *_forbidden("x.com", "twitter.com", "t.co", platform="X"),
    *_forbidden("youtube.com", "youtu.be", platform="YouTube"),
    *_forbidden("reddit.com", platform="Reddit"),
    *_forbidden("pinterest.com", platform="Pinterest"),
    # --- Competitive programming and data ---------------------------------
    *_forbidden("leetcode.com", "leetcode.cn", platform="LeetCode"),
    *_no_api("hackerrank.com", platform="HackerRank"),
    *_forbidden("codechef.com", platform="CodeChef"),
    *_forbidden("kaggle.com", platform="Kaggle"),
    *_no_api("hackerearth.com", "topcoder.com", platform="this coding platform"),
    # --- Design and creative ----------------------------------------------
    *_no_api("behance.net", platform="Behance"),
    *_no_api("dribbble.com", platform="Dribbble"),
    *_client_rendered("figma.com", platform="Figma"),
    *_client_rendered("artstation.com", platform="ArtStation"),
    *_no_api("deviantart.com", platform="DeviantArt"),
    *_no_api("500px.com", platform="500px"),
    # --- Writing and publishing -------------------------------------------
    *_no_api("medium.com", platform="Medium"),
    *_no_api("quora.com", platform="Quora"),
    *_forbidden("goodreads.com", platform="Goodreads"),
    # --- Freelance marketplaces -------------------------------------------
    *_forbidden("upwork.com", platform="Upwork"),
    *_forbidden("fiverr.com", platform="Fiverr"),
    *_forbidden("toptal.com", platform="Toptal"),
    # --- Research and academia --------------------------------------------
    # ResearchGate answers automated requests with 403; Google Scholar is
    # consent- and captcha-walled and its terms forbid automated access. Both
    # are covered instead by the OpenAlex connector when the user supplies an
    # ORCID iD, which is an open, CC0 source for the same publication record.
    *_forbidden("researchgate.net", platform="ResearchGate"),
    *_forbidden("scholar.google.com", platform="Google Scholar"),
    *_forbidden("academia.edu", platform="Academia.edu"),
    *_no_api("ssrn.com", "papers.ssrn.com", platform="SSRN"),
    *_no_api("webofscience.com", "publons.com", "scopus.com", platform="this citation index"),
    # --- Regulated professional registers ---------------------------------
    # Public and citable, but they are identity registers, not achievement
    # feeds; several also carry personal data Rezumi has no reason to ingest.
    *_register("brokercheck.finra.org", platform="FINRA BrokerCheck"),
    *_register("adviserinfo.sec.gov", platform="SEC IAPD"),
    *_register("npiregistry.cms.hhs.gov", platform="the NPI Registry"),
    *_register("doximity.com", platform="Doximity"),
    *_register("avvo.com", "martindale.com", platform="this legal directory"),
    # --- Learning platforms ------------------------------------------------
    # Certificate pages here are client-rendered; Credly and Accredible remain
    # the machine-readable route for the same credentials.
    *_client_rendered("coursera.org", platform="Coursera"),
    *_client_rendered("udemy.com", platform="Udemy"),
    *_client_rendered("edx.org", platform="edX"),
    *_client_rendered("datacamp.com", platform="DataCamp"),
    *_client_rendered("pluralsight.com", platform="Pluralsight"),
    *_client_rendered("trailblazer.me", platform="Salesforce Trailhead"),
    *_client_rendered("cloudskillsboost.google", platform="Google Cloud Skills Boost"),
)

# Hosts owned by a dedicated API connector. The portfolio fallback must never
# claim these: scraping a rendered GitHub or Stack Exchange page yields
# navigation chrome instead of the documented API's real profile data.
API_PLATFORM_DOMAINS: tuple[str, ...] = (
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "stackoverflow.com",
    "stackexchange.com",
    "serverfault.com",
    "superuser.com",
    "askubuntu.com",
    "mathoverflow.net",
    "stackapps.com",
    "codeforces.com",
    "dev.to",
    "huggingface.co",
    "hub.docker.com",
    "credly.com",
    "youracclaim.com",
    "orcid.org",
    "openalex.org",
    "example.test",
)

UNSUPPORTED_LINK_MESSAGE = (
    "This link type is not supported for automatic enrichment yet. GitHub, "
    "GitLab, Bitbucket, the Stack Exchange network, Codeforces, dev.to, "
    "Credly, Hugging Face, Docker Hub, ORCID/OpenAlex research profiles, and public portfolio or "
    "personal-site links are supported. The link stays on your record as "
    "evidence either way."
)


def blocked_platform_reason(url: str) -> str | None:
    """Return why ``url``'s platform may not be read automatically, if blocked."""

    host = hostname(url)
    for domain, reason in BLOCKED_PLATFORMS:
        if host_matches(host, domain):
            return reason
    return None


def is_api_platform_host(url: str) -> bool:
    """Whether a dedicated API connector owns this host (or any subdomain)."""

    host = hostname(url)
    return any(host_matches(host, domain) for domain in API_PLATFORM_DOMAINS)
