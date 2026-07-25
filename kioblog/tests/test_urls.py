import importlib

from django.test import SimpleTestCase, override_settings
from django.urls import resolve, clear_url_caches
from django.urls.exceptions import Resolver404

from kioblog import urls as kioblog_urls


class MediaServingTests(SimpleTestCase):
    def test_urls_have_no_catch_all_even_with_degenerate_media_url(self) -> None:
        # kioblog/urls.py used to build urlpatterns (including a static()
        # call) from settings.MEDIA_URL at import time. override_settings
        # alone doesn't re-run that module-level code or invalidate Django's
        # cached URLResolver, so a stale resolver built from the real
        # MEDIA_URL would make this assertion pass even if the vulnerable
        # code came back - we reload the module and clear the URL cache
        # ourselves while the override is active so the test actually
        # observes what a real MEDIA_URL='/' consumer would get.
        try:
            with override_settings(DEBUG=True, MEDIA_URL='/'):
                importlib.reload(kioblog_urls)
                clear_url_caches()
                with self.assertRaises(Resolver404):
                    resolve('/some/nested/arbitrary/path', urlconf='kioblog.urls')
        finally:
            importlib.reload(kioblog_urls)
            clear_url_caches()
