"""Multi-source fetch with ranking, deduplication, and resilient error handling."""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _extract_domain(url: str) -> str:
    """Extract domain from URL for diversity checking."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:  # pylint: disable=broad-except
        return ""


def _rank_and_deduplicate(
    search_results: List[Dict[str, Any]],
    max_sources: int = 3,
    max_per_domain: int = 1,
) -> List[Dict[str, Any]]:
    """Rank search results and enforce source diversity.
    
    Args:
        search_results: List of search results with 'url', 'title', 'snippet'
        max_sources: Maximum number of sources to return
        max_per_domain: Maximum URLs from same domain
        
    Returns:
        Ranked and deduplicated list of sources
    """
    if not search_results:
        return []
    
    seen_urls: Set[str] = set()
    domain_counts: Dict[str, int] = {}
    ranked: List[Dict[str, Any]] = []
    
    for result in search_results:
        url = result.get("url", "").strip()
        if not url or url in seen_urls:
            continue
        
        domain = _extract_domain(url)
        if not domain:
            continue
        
        # Enforce domain diversity
        if domain_counts.get(domain, 0) >= max_per_domain:
            logger.debug("Skipping %s (domain %s already has %d URLs)", url, domain, max_per_domain)
            continue
        
        seen_urls.add(url)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        ranked.append(result)
        
        if len(ranked) >= max_sources:
            break
    
    return ranked


async def multi_fetch(
    search_results: List[Dict[str, Any]],
    fetch_fn: Callable[[str], Any],
    max_sources: int = 3,
    max_per_domain: int = 1,
    timeout_per_fetch: float = 10.0,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Fetch content from multiple sources with error handling and diversity.
    
    Args:
        search_results: List of search results with 'url', 'title', 'snippet'
        fetch_fn: Async or sync function that takes URL and returns fetch result
        max_sources: Maximum number of sources to fetch
        max_per_domain: Maximum URLs from same domain
        timeout_per_fetch: Timeout per fetch operation in seconds
        
    Returns:
        Tuple of (successful_fetches, failed_urls)
        successful_fetches: List of dicts with 'url', 'content', 'title'
        failed_urls: List of URLs that failed to fetch
    """
    ranked = _rank_and_deduplicate(search_results, max_sources, max_per_domain)
    
    if not ranked:
        logger.warning("No sources to fetch after ranking/dedup")
        return [], []
    
    logger.info("Multi-fetch: attempting %d sources (max_sources=%d, max_per_domain=%d)", 
                len(ranked), max_sources, max_per_domain)
    
    successful: List[Dict[str, Any]] = []
    failed: List[str] = []
    
    for idx, result in enumerate(ranked, 1):
        url = result.get("url", "")
        title = result.get("title", "")
        
        logger.info("[%d/%d] Fetching: %s", idx, len(ranked), url)
        
        try:
            # Execute fetch with timeout
            # Check if fetch_fn returns a coroutine
            result = fetch_fn(url)
            if asyncio.iscoroutine(result):
                fetch_result = await asyncio.wait_for(
                    result,
                    timeout=timeout_per_fetch,
                )
            else:
                fetch_result = await asyncio.wait_for(
                    asyncio.to_thread(lambda: result),
                    timeout=timeout_per_fetch,
                )
            
            # Check if fetch was successful
            if isinstance(fetch_result, dict):
                if fetch_result.get("ok") is False:
                    error_msg = fetch_result.get("error", "Unknown error")
                    logger.warning("[%d/%d] Fetch failed: %s - %s", idx, len(ranked), url, error_msg)
                    failed.append(url)
                    continue
                
                content = fetch_result.get("result", "")
                if not content or (isinstance(content, str) and len(content.strip()) < 50):
                    logger.warning("[%d/%d] Fetch returned empty/short content: %s", idx, len(ranked), url)
                    failed.append(url)
                    continue
                
                successful.append({
                    "url": url,
                    "title": title,
                    "content": content,
                    "domain": _extract_domain(url),
                })
                logger.info("[%d/%d] ✓ Fetch successful: %s (%d chars)", 
                           idx, len(ranked), url, len(str(content)))
            else:
                logger.warning("[%d/%d] Fetch returned unexpected format: %s", idx, len(ranked), url)
                failed.append(url)
        
        except asyncio.TimeoutError:
            logger.warning("[%d/%d] Fetch timeout: %s", idx, len(ranked), url)
            failed.append(url)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[%d/%d] Fetch error: %s - %s", idx, len(ranked), url, exc)
            failed.append(url)
    
    logger.info("Multi-fetch complete: %d successful, %d failed", len(successful), len(failed))
    return successful, failed


def synthesize_multi_source(
    user_query: str,
    fetched_sources: List[Dict[str, Any]],
    llm_call: Callable[[str], str],
) -> str:
    """Synthesize answer from multiple sources using LLM.
    
    Args:
        user_query: Original user query
        fetched_sources: List of dicts with 'url', 'content', 'title', 'domain'
        llm_call: Function to call LLM with prompt
        
    Returns:
        Synthesized response with citations
    """
    if not fetched_sources:
        return "I was unable to retrieve content from any sources."
    
    # Build context from all sources
    context_parts = []
    for idx, source in enumerate(fetched_sources, 1):
        content_str = str(source.get("content", ""))
        content = content_str[:2000] if len(content_str) > 2000 else content_str  # Limit per source
        title = source.get("title", "")
        domain = source.get("domain", "")
        
        context_parts.append(f"Source {idx} ({domain}):")
        if title:
            context_parts.append(f"Title: {title}")
        context_parts.append(f"Content: {content}")
        context_parts.append("")
    
    context = "\n".join(context_parts)
    
    # Build synthesis prompt
    prompt = f"""The user asked: {user_query}

I retrieved content from {len(fetched_sources)} sources:

{context}

Provide a comprehensive answer that:
1. Synthesizes information from ALL sources
2. Uses bullet points for key findings
3. Includes source citations at the end (list domains only)
4. Is conversational and easy to understand
5. Highlights any conflicting information between sources

Format:
[Main answer with bullet points]

Sources:
• domain1.com
• domain2.com
• domain3.com"""
    
    try:
        response = llm_call(prompt)
        return response
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Synthesis failed: %s", exc)
        # Fallback: return first source content
        first = fetched_sources[0]
        return f"Based on {first.get('domain', 'source')}:\n\n{str(first.get('content', ''))[:1000]}"
