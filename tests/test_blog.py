"""
Tests for blog routes and sitemap.

Verifies:
- Blog article routes return 200
- Blog landing page lists articles
- Sitemap includes blog URLs
"""


class TestBlogArticleRoute:
    """Blog article route /blog/best-time-to-export-octopus-agile-outgoing"""

    def test_route_returns_200(self, client):
        r = client.get("/blog/best-time-to-export-octopus-agile-outgoing")
        assert r.status_code == 200

    def test_page_contains_h1(self, client):
        r = client.get("/blog/best-time-to-export-octopus-agile-outgoing")
        assert b"Best Time to Export Power on Octopus Agile Outgoing" in r.data

    def test_page_contains_export_link(self, client):
        r = client.get("/blog/best-time-to-export-octopus-agile-outgoing")
        assert b"/export" in r.data

    def test_page_contains_2025_stats_section(self, client):
        r = client.get("/blog/best-time-to-export-octopus-agile-outgoing")
        assert b"What 2025 Export Data Shows" in r.data


class TestAgileVsFixedBlogArticle:
    """Blog article route /blog/octopus-agile-outgoing-vs-fixed-outgoing"""

    def test_route_returns_200(self, client):
        r = client.get("/blog/octopus-agile-outgoing-vs-fixed-outgoing")
        assert r.status_code == 200

    def test_page_contains_h1(self, client):
        r = client.get("/blog/octopus-agile-outgoing-vs-fixed-outgoing")
        assert b"Agile Outgoing vs Fixed Outgoing Octopus" in r.data

    def test_page_contains_comparison_table(self, client):
        r = client.get("/blog/octopus-agile-outgoing-vs-fixed-outgoing")
        assert b"Fixed Outgoing" in r.data
        assert b"Agile Outgoing" in r.data
        assert b"12p per kWh" in r.data

    def test_page_contains_export_link(self, client):
        r = client.get("/blog/octopus-agile-outgoing-vs-fixed-outgoing")
        assert b"/export" in r.data

    def test_page_contains_referral_cta(self, client):
        r = client.get("/blog/octopus-agile-outgoing-vs-fixed-outgoing")
        assert b"Switch to Octopus Energy" in r.data


class TestBlogLandingPage:
    """Blog index /blog"""

    def test_blog_index_returns_200(self, client):
        r = client.get("/blog")
        assert r.status_code == 200

    def test_blog_index_lists_export_article(self, client):
        r = client.get("/blog")
        assert b"Best Time to Export on Octopus Agile Outgoing" in r.data

    def test_blog_index_links_to_export_article(self, client):
        r = client.get("/blog")
        assert b"/blog/best-time-to-export-octopus-agile-outgoing" in r.data

    def test_blog_index_lists_agile_vs_fixed_article(self, client):
        r = client.get("/blog")
        assert b"Agile Outgoing vs Fixed Outgoing Octopus" in r.data

    def test_blog_index_links_to_agile_vs_fixed_article(self, client):
        r = client.get("/blog")
        assert b"/blog/octopus-agile-outgoing-vs-fixed-outgoing" in r.data

    def test_blog_index_contains_structured_data(self, client):
        r = client.get("/blog")
        assert b'application/ld+json' in r.data
        assert b'"@type":"Blog"' in r.data or b'"@type": "Blog"' in r.data
        assert b'"@type":"BlogPosting"' in r.data or b'"@type": "BlogPosting"' in r.data


class TestSitemap:
    """Sitemap /sitemap.xml"""

    def test_sitemap_returns_200(self, client):
        r = client.get("/sitemap.xml")
        assert r.status_code == 200

    def test_sitemap_includes_export_blog_url(self, client):
        r = client.get("/sitemap.xml")
        assert b"/blog/best-time-to-export-octopus-agile-outgoing" in r.data

    def test_sitemap_includes_agile_vs_fixed_blog_url(self, client):
        r = client.get("/sitemap.xml")
        assert b"/blog/octopus-agile-outgoing-vs-fixed-outgoing" in r.data
