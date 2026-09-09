"""Source validation used before a discovered item can enter the pipeline."""

from urllib.parse import urlparse


TRUSTED_SOURCE_DOMAINS = {
    "arxiv.org",
    "github.com",
    "deepmind.google",
    "huggingface.co",
    "openai.com",
    "anthropic.com",
    "ai.google",
    "developers.googleblog.com",
    "microsoft.com",
    "techcrunch.com",
    "theverge.com",
    "venturebeat.com",
}


def verify_source(url: str) -> bool:
    """Reject malformed or non-web source URLs before persistence."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    hostname = parsed.hostname.lower().removeprefix("www.") if parsed.hostname else ""
    return hostname in TRUSTED_SOURCE_DOMAINS or any(
        hostname.endswith(f".{domain}") for domain in TRUSTED_SOURCE_DOMAINS
    )
