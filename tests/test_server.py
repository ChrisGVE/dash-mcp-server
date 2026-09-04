import json

from dash_mcp_server.server import (
    SearchResult,
    estimate_tokens,
    extract_section,
    parse_fragment,
)


class TestParseFragment:
    def test_dash_ref_fragment(self):
        url = "http://127.0.0.1:1234/Dash/abc/Enumerable.html#//dash_ref_method%2Di%2Dsort%5Fby/Method/sort_by/0"
        assert parse_fragment(url) == "method-i-sort_by"

    def test_plain_fragment(self):
        url = "http://127.0.0.1:1234/page.html#some-anchor"
        assert parse_fragment(url) == "some-anchor"

    def test_no_fragment(self):
        url = "http://127.0.0.1:1234/page.html"
        assert parse_fragment(url) is None

    def test_empty_fragment(self):
        url = "http://127.0.0.1:1234/page.html#"
        assert parse_fragment(url) is None


class TestExtractSection:
    FULL_PAGE = """
    <html><body>
      <nav><a href="/">Home</a><a href="/docs">Docs</a></nav>
      <aside class="sidebar"><ul><li>Item</li></ul></aside>
      <div id="method-i-sort_by">
        <h2>sort_by</h2>
        <p>Sorts by the block return value.</p>
      </div>
      <div id="method-i-map">
        <h2>map</h2>
        <p>Maps elements.</p>
      </div>
    </body></html>
    """

    def test_extracts_anchor_section(self):
        result = extract_section(self.FULL_PAGE, "method-i-sort_by")
        assert "sort_by" in result
        assert "Sorts by the block return value" in result
        assert "Maps elements" not in result

    def test_strips_nav_when_no_anchor(self):
        result = extract_section(self.FULL_PAGE, None)
        assert "<nav>" not in result
        assert "Home" not in result
        assert "sort_by" in result
        assert "Maps elements" in result

    def test_strips_sidebar_when_no_anchor(self):
        result = extract_section(self.FULL_PAGE, None)
        assert "sidebar" not in result

    def test_falls_back_to_nav_strip_when_anchor_not_found(self):
        result = extract_section(self.FULL_PAGE, "nonexistent-anchor")
        assert "<nav>" not in result
        assert "sort_by" in result

    def test_walks_up_from_thin_anchor_element(self):
        html = """
        <html><body>
          <div id="method-wrapper">
            <a id="method-i-foo"></a>
            <h2>foo</h2>
            <p>Foo description.</p>
          </div>
        </body></html>
        """
        result = extract_section(html, "method-i-foo")
        assert "Foo description" in result

    def test_walks_up_falls_back_when_no_block_parent(self):
        html = """
        <html><body>
          <nav><a href="/">Home</a></nav>
          <a id="orphan-anchor"></a>
          <p>Content with no block wrapper.</p>
        </body></html>
        """
        result = extract_section(html, "orphan-anchor")
        # No suitable block parent, so falls back to nav-stripping
        assert "<nav>" not in result
        assert "Content with no block wrapper" in result


class TestEstimateTokens:
    def test_estimate_counts_json_structure_not_just_field_lengths(self):
        result = SearchResult(
            name="fastapi.Depends",
            type="Function",
            platform=None,
            load_url="https://fastapi.tiangolo.com/reference/dependencies/index.html#fastapi.Depends",
            docset="FastAPI",
            description=None,
            language=None,
            tags=None,
        )
        serialized = json.dumps(result.model_dump())
        # The estimate must track what is actually sent, within rounding of the 4-chars
        # heuristic. Summing field lengths alone lands ~30% low on a record like this.
        assert estimate_tokens(result) == max(1, len(serialized) // 4)

    def test_estimate_scales_with_a_list_of_records(self):
        results = [
            SearchResult(
                name=f"symbol_{i}",
                type="Function",
                platform=None,
                load_url=f"https://example.com/docs/index.html#symbol_{i}",
                docset="Example",
                description=None,
                language=None,
                tags=None,
            )
            for i in range(50)
        ]
        one = estimate_tokens(results[0])
        many = estimate_tokens(results)
        assert many >= 50 * one * 0.9

    def test_estimate_handles_plain_types(self):
        assert estimate_tokens("") == 1
        assert estimate_tokens("a" * 400) >= 100
        assert estimate_tokens({"k": "v"}) >= 1
        assert estimate_tokens(None) == 1

    def test_estimate_survives_a_non_serializable_value(self):
        assert estimate_tokens({"when": object()}) >= 1
