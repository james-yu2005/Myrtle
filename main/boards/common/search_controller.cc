#include "search_controller.h"

#include "board.h"
#include "settings.h"

#include <cJSON.h>
#include <esp_log.h>
#include <sdkconfig.h>

#include <stdexcept>

static const char* TAG = "SearchController";

SearchController& SearchController::GetInstance() {
    static SearchController instance;
    return instance;
}

void SearchController::Initialize() {
    auto& mcp_server = McpServer::GetInstance();

    mcp_server.AddTool(
        "self.search.web",
        "Search the live web with Tavily and return source snippets for the LLM to summarize. "
        "Use this when the user asks for current information, news, stock prices, how-tos, or "
        "anything that needs an online search. Pass a clear natural-language query. "
        "Keep queries short. This tool must finish quickly.",
        PropertyList({
            Property("query", kPropertyTypeString),
            Property("max_results", kPropertyTypeInteger, 3, 1, 5),
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            auto query = properties["query"].value<std::string>();
            int max_results = properties["max_results"].value<int>();
            if (query.empty()) {
                throw std::runtime_error("query must not be empty");
            }
            return Search(query, max_results);
        });

    mcp_server.AddUserOnlyTool(
        "self.search.set_api_key",
        "Store the Tavily API key on the device (NVS). User-only action.",
        PropertyList({
            Property("api_key", kPropertyTypeString),
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            auto api_key = properties["api_key"].value<std::string>();
            if (api_key.empty()) {
                throw std::runtime_error("api_key must not be empty");
            }
            SetApiKey(api_key);
            return true;
        });

    mcp_server.AddUserOnlyTool(
        "self.search.status",
        "Whether a Tavily API key is configured on the device. Does not return the key.",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            (void)properties;
            cJSON* json = cJSON_CreateObject();
            cJSON_AddBoolToObject(json, "configured", HasApiKey());
            cJSON_AddStringToObject(json, "provider", "tavily");
            char* json_str = cJSON_PrintUnformatted(json);
            std::string result(json_str);
            cJSON_free(json_str);
            cJSON_Delete(json);
            return result;
        });

    ESP_LOGI(TAG, "SearchController initialized (api key %s)",
             HasApiKey() ? "configured" : "missing");
}

bool SearchController::HasApiKey() const {
    return !GetApiKey().empty();
}

void SearchController::SetApiKey(const std::string& api_key) {
    Settings settings("search", true);
    settings.SetString("tavily_key", api_key);
    ESP_LOGI(TAG, "Tavily API key saved to NVS");
}

std::string SearchController::GetApiKey() const {
    Settings settings("search", false);
    std::string key = settings.GetString("tavily_key");
    if (!key.empty()) {
        return key;
    }
#ifdef CONFIG_TAVILY_API_KEY
    if (CONFIG_TAVILY_API_KEY[0] != '\0') {
        return CONFIG_TAVILY_API_KEY;
    }
#endif
    return "";
}

std::string SearchController::Search(const std::string& query, int max_results) {
    std::string api_key = GetApiKey();
    if (api_key.empty()) {
        throw std::runtime_error(
            "Tavily API key not configured. Set CONFIG_TAVILY_API_KEY or call "
            "self.search.set_api_key");
    }

    if (max_results < 1) {
        max_results = 1;
    }
    if (max_results > 5) {
        max_results = 5;
    }

    // Fast path: no include_answer (xiaozhi LLM summarizes snippets).
    // Cloud MCP tool timeout is ~10s — stay well under that.
    cJSON* body = cJSON_CreateObject();
    cJSON_AddStringToObject(body, "query", query.c_str());
    cJSON_AddStringToObject(body, "search_depth", "fast");
    cJSON_AddNumberToObject(body, "max_results", max_results);
    cJSON_AddBoolToObject(body, "include_answer", false);
    cJSON_AddBoolToObject(body, "include_images", false);
    cJSON_AddBoolToObject(body, "include_raw_content", false);
    char* body_str = cJSON_PrintUnformatted(body);
    std::string request_body(body_str);
    cJSON_free(body_str);
    cJSON_Delete(body);

    auto network = Board::GetInstance().GetNetwork();
    if (network == nullptr) {
        throw std::runtime_error("Network not available");
    }

    auto http = network->CreateHttp(0);
    http->SetTimeout(8000);
    http->SetHeader("Content-Type", "application/json");
    http->SetHeader("Authorization", "Bearer " + api_key);
    http->SetContent(std::move(request_body));

    ESP_LOGI(TAG, "Searching Tavily: %s", query.c_str());
    if (!http->Open("POST", kTavilySearchUrl)) {
        throw std::runtime_error("Failed to connect to Tavily API (timeout or network error)");
    }

    int status = http->GetStatusCode();
    std::string response = http->ReadAll();
    http->Close();

    if (status != 200) {
        ESP_LOGE(TAG, "Tavily HTTP %d: %s", status, response.c_str());
        throw std::runtime_error("Tavily search failed with HTTP " + std::to_string(status));
    }

    ESP_LOGI(TAG, "Tavily response %u bytes", (unsigned)response.size());
    return CompactResponse(response);
}

std::string SearchController::CompactResponse(const std::string& raw_json) const {
    cJSON* root = cJSON_Parse(raw_json.c_str());
    if (root == nullptr) {
        throw std::runtime_error("Failed to parse Tavily response");
    }

    cJSON* out = cJSON_CreateObject();

    cJSON* answer = cJSON_GetObjectItem(root, "answer");
    if (cJSON_IsString(answer) && answer->valuestring != nullptr) {
        cJSON_AddStringToObject(out, "answer", answer->valuestring);
    }

    cJSON* results_out = cJSON_CreateArray();
    cJSON* results = cJSON_GetObjectItem(root, "results");
    if (cJSON_IsArray(results)) {
        cJSON* item = nullptr;
        cJSON_ArrayForEach(item, results) {
            cJSON* entry = cJSON_CreateObject();

            cJSON* title = cJSON_GetObjectItem(item, "title");
            if (cJSON_IsString(title) && title->valuestring != nullptr) {
                cJSON_AddStringToObject(entry, "title", title->valuestring);
            }

            cJSON* url = cJSON_GetObjectItem(item, "url");
            if (cJSON_IsString(url) && url->valuestring != nullptr) {
                cJSON_AddStringToObject(entry, "url", url->valuestring);
            }

            cJSON* content = cJSON_GetObjectItem(item, "content");
            if (cJSON_IsString(content) && content->valuestring != nullptr) {
                std::string snippet(content->valuestring);
                if (snippet.size() > kMaxSnippetChars) {
                    snippet.resize(kMaxSnippetChars);
                    snippet.append("...");
                }
                cJSON_AddStringToObject(entry, "content", snippet.c_str());
            }

            cJSON_AddItemToArray(results_out, entry);
        }
    }
    cJSON_AddItemToObject(out, "results", results_out);

    char* out_str = cJSON_PrintUnformatted(out);
    std::string result(out_str ? out_str : "");
    cJSON_free(out_str);
    cJSON_Delete(out);
    cJSON_Delete(root);

    if (result.size() > kMaxResponseChars) {
        result.resize(kMaxResponseChars);
        result.append("...");
    }
    return result;
}
