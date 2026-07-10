from django.test import SimpleTestCase

from kioblog.markdown.render import render_markdown


class RenderMarkdownTests(SimpleTestCase):
    def test_code_fence_emits_chrome_contract(self) -> None:
        html = render_markdown('```python:accounts/views.py\nprint(1)\n```').html
        # DOM contract from SPEC section 5 - class names must not change.
        self.assertIn('<figure class="code-block" data-lang="python">', html)
        self.assertIn('<div class="code-block__bar">', html)
        self.assertIn('<span class="code-block__dots"><i></i><i></i><i></i></span>', html)
        self.assertIn('<span class="code-block__file">accounts/views.py</span>', html)
        self.assertIn('<span class="code-block__lang">python</span>', html)
        self.assertIn('<button class="code-block__copy" type="button">Copy</button>', html)
        self.assertIn('<pre class="code-block__gutter" aria-hidden="true">', html)
        self.assertIn('<div class="highlight">', html)

    def test_fence_without_info_defaults_to_text_and_omits_file(self) -> None:
        html = render_markdown('```\nplain\n```').html
        self.assertIn('data-lang="text"', html)
        self.assertNotIn('code-block__file', html)

    def test_gutter_has_one_number_per_line(self) -> None:
        html = render_markdown('```\na\nb\nc\n```').html
        gutter = html.split('code-block__gutter" aria-hidden="true">')[1].split('</pre>')[0]
        self.assertEqual(gutter.split('\n'), ['1', '2', '3'])

    def test_toc_built_from_headings(self) -> None:
        rendered = render_markdown('# One\n\n## Two\n')
        self.assertIn('#two', rendered.toc)

    def test_pygments_highlights_tokens(self) -> None:
        html = render_markdown('```python\ndef f():\n    pass\n```').html
        self.assertIn('class="k"', html)  # keyword token
