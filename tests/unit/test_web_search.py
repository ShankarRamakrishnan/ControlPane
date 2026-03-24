"""Unit tests for the web_search tool (tools/web_search.py)."""
import pytest
from unittest.mock import MagicMock, patch


class TestTavilySearch:
    def test_returns_formatted_results(self):
        from tools.web_search import _tavily_search

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "content": "Content one " * 20},
                {"title": "Result 2", "url": "https://example.com/2", "content": "Content two " * 20},
            ]
        }

        with patch("tools.web_search.httpx.post", return_value=mock_resp) as mock_post:
            result = _tavily_search("test query", "fake-key")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["query"] == "test query"
        assert call_kwargs[1]["json"]["api_key"] == "fake-key"

        assert "Result 1" in result
        assert "https://example.com/1" in result

    def test_returns_no_results_message(self):
        from tools.web_search import _tavily_search

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"results": []}

        with patch("tools.web_search.httpx.post", return_value=mock_resp):
            result = _tavily_search("empty query", "fake-key")

        assert result == "No results found."

    def test_handles_http_error(self):
        from tools.web_search import _tavily_search
        import httpx

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        )

        with patch("tools.web_search.httpx.post", return_value=mock_resp):
            result = _tavily_search("query", "bad-key")

        assert "Search error" in result or "error" in result.lower()

    def test_handles_connection_error(self):
        from tools.web_search import _tavily_search

        with patch("tools.web_search.httpx.post", side_effect=Exception("timeout")):
            result = _tavily_search("query", "key")

        assert "Search error" in result

    def test_truncates_content_to_200_chars(self):
        from tools.web_search import _tavily_search

        long_content = "x" * 500
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "results": [{"title": "T", "url": "u", "content": long_content}]
        }

        with patch("tools.web_search.httpx.post", return_value=mock_resp):
            result = _tavily_search("q", "k")

        # Content should be truncated at 200 chars in the output
        assert len(result) < len(long_content)


class TestDuckDuckGoSearch:
    def test_returns_abstract_text(self):
        from tools.web_search import _duckduckgo_search

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "AbstractText": "Python is a programming language.",
            "RelatedTopics": [],
        }

        with patch("tools.web_search.httpx.get", return_value=mock_resp):
            result = _duckduckgo_search("python")

        assert result == "Python is a programming language."

    def test_falls_back_to_related_topics(self):
        from tools.web_search import _duckduckgo_search

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "AbstractText": "",
            "RelatedTopics": [
                {"Text": "Related topic A"},
                {"Text": "Related topic B"},
            ],
        }

        with patch("tools.web_search.httpx.get", return_value=mock_resp):
            result = _duckduckgo_search("query")

        assert "Related topic A" in result
        assert "Related topic B" in result

    def test_returns_no_results_when_empty(self):
        from tools.web_search import _duckduckgo_search

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"AbstractText": "", "RelatedTopics": []}

        with patch("tools.web_search.httpx.get", return_value=mock_resp):
            result = _duckduckgo_search("obscure query")

        assert result == "No results found."

    def test_skips_non_dict_related_topics(self):
        from tools.web_search import _duckduckgo_search

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "AbstractText": "",
            "RelatedTopics": [
                "not a dict",
                {"Text": "Valid topic"},
                {"NoText": "also invalid"},
            ],
        }

        with patch("tools.web_search.httpx.get", return_value=mock_resp):
            result = _duckduckgo_search("q")

        assert "Valid topic" in result

    def test_handles_http_error(self):
        from tools.web_search import _duckduckgo_search
        import httpx

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        with patch("tools.web_search.httpx.get", return_value=mock_resp):
            result = _duckduckgo_search("q")

        assert "Search error" in result

    def test_handles_connection_error(self):
        from tools.web_search import _duckduckgo_search

        with patch("tools.web_search.httpx.get", side_effect=Exception("network down")):
            result = _duckduckgo_search("q")

        assert "Search error" in result


class TestWebSearchProviderSelection:
    def test_uses_tavily_when_key_present(self, monkeypatch):
        from tools.web_search import _tavily_search, _duckduckgo_search

        monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")

        with patch("tools.web_search._tavily_search", return_value="tavily result") as mock_tavily, \
             patch("tools.web_search._duckduckgo_search") as mock_ddg:
            from tools.web_search import web_search
            result = web_search.invoke({"query": "test"})

        mock_tavily.assert_called_once_with("test", "test-tavily-key")
        mock_ddg.assert_not_called()

    def test_uses_duckduckgo_when_no_tavily_key(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        with patch("tools.web_search._duckduckgo_search", return_value="ddg result") as mock_ddg, \
             patch("tools.web_search._tavily_search") as mock_tavily:
            from tools.web_search import web_search
            result = web_search.invoke({"query": "test"})

        mock_ddg.assert_called_once_with("test")
        mock_tavily.assert_not_called()


class TestWebSearchToolMetadata:
    def test_tool_name(self):
        from tools.web_search import web_search
        assert web_search.name == "web_search"

    def test_tool_description(self):
        from tools.web_search import web_search
        assert "search" in web_search.description.lower()
