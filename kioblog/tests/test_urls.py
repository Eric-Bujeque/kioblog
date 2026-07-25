from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from django.urls.exceptions import Resolver404


class MediaServingTests(SimpleTestCase):
    @override_settings(DEBUG=True, MEDIA_URL='/')
    def test_urls_have_no_catch_all_even_with_degenerate_media_url(self) -> None:
        # Regression test: kioblog/urls.py used to do
        # `urlpatterns += static(settings.MEDIA_URL, ...)`. Django's static()
        # only rejects an empty prefix, so a consumer with MEDIA_URL='/' (falsy
        # check passes, but .lstrip('/') reduces it to '') got a
        # ^(?P<path>.*)$ catch-all serving arbitrary files under wherever
        # kioblog.urls is mounted. Serving MEDIA in DEBUG is the consumer
        # project's responsibility (see kioblogdev/urls.py), not the app's.
        with self.assertRaises(Resolver404):
            resolve('/some/nested/arbitrary/path', urlconf='kioblog.urls')
