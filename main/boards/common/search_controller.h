#ifndef SEARCH_CONTROLLER_H
#define SEARCH_CONTROLLER_H

#include "mcp_server.h"

#include <string>

// On-device web search via Tavily REST API (no Mac MCP host required).
class SearchController {
public:
    static SearchController& GetInstance();

    void Initialize();

    // Returns compact JSON for the LLM, or throws on failure.
    std::string Search(const std::string& query, int max_results = 5);

    bool HasApiKey() const;
    void SetApiKey(const std::string& api_key);

private:
    SearchController() = default;

    std::string GetApiKey() const;
    std::string CompactResponse(const std::string& raw_json) const;

    static constexpr const char* kTavilySearchUrl = "https://api.tavily.com/search";
    static constexpr size_t kMaxSnippetChars = 280;
    static constexpr size_t kMaxResponseChars = 3500;
};

#endif  // SEARCH_CONTROLLER_H
