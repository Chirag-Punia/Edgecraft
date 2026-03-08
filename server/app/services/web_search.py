"""Web search service using Tavily API for external information retrieval."""
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def search_web(query: str, max_results: int = 5) -> dict:
    """Search the web and return structured results.

    Returns:
        {
            "query": str,
            "results": [{"title": str, "url": str, "content": str}],
            "answer": str,
        }
    """
    if not settings.TAVILY_API_KEY:
        return {
            "query": query,
            "results": [],
            "answer": "Web search is not configured. Please set TAVILY_API_KEY.",
        }

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )
        return {
            "query": query,
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],
                }
                for r in response.get("results", [])
            ],
            "answer": response.get("answer", ""),
        }
    except Exception as e:
        logger.error("Web search failed: %s", e)
        return {
            "query": query,
            "results": [],
            "answer": "Web search is temporarily unavailable. Please try again.",
        }
