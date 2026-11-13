
import os
from urllib.parse import urlsplit

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


def research_claim(claim: str) -> dict:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("Tavily API key is missing. Set TAVILY_API_KEY in .env.")

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=f"Current and reliable information about: {claim}",
            search_depth="basic",
            max_results=5,
            include_answer=True
        )

        results = []

        for item in response.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str):
                continue
            parsed_url = urlsplit(url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                continue

            results.append({
                "title": str(item.get("title") or "Source"),
                "url": item.get("url", ""),
                "content": str(item.get("content") or ""),
                "score": item.get("score"),
            })

        return {
            "claim": claim,
            "search_answer": str(response.get("answer") or ""),
            "sources": results,
        }

    except Exception as error:
        raise RuntimeError(
            "Tavily research failed. Check the service, network connection, "
            "and TAVILY_API_KEY configuration."
        ) from error
