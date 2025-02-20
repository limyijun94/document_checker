# pydantic_googleaddon/web_search.py

class WebSearch:
    def __init__(self, agent, web_tool):
        self.agent = agent
        self.web_tool = web_tool
        # Register the search and browse capabilities
        agent.register_tool(self.search, "search", "Search the web for information")
        agent.register_tool(self.browse, "browse", "Get content from a specific URL")

    async def search(self, query: str) -> str:
        """Search the web and return results."""
        results = self.web_tool.search(query)
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   Description: {result['description']}\n"
            )
        return "\n".join(formatted_results)

    async def browse(self, url: str) -> str:
        """Get content from a specific URL."""
        if not self.web_tool.is_url(url):
            return f"Invalid URL: {url}"
        
        content = self.web_tool.get_web_content(url)
        if not content:
            return f"Could not retrieve content from {url}"
        
        return content
