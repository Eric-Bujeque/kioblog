"""Markdown -> HTML rendering pipeline for post content.

``render_markdown`` returns a :class:`RenderedContent` exposing the rendered
``html`` (with the code chrome from :mod:`kioblog.markdown.code_chrome`) and the
``toc`` table of contents derived from the ``<h2>`` headings, used for the
"On this page" index. Also wired as ``MARKDOWNX_MARKDOWNIFY_FUNCTION`` so the
admin preview matches the public render.
"""

import markdown
from markdown.extensions.toc import TocExtension

from kioblog.markdown.code_chrome import CodeChromeExtension


class RenderedContent(str):
    """A rendered HTML string that also carries the generated ``toc``.

    Subclasses ``str`` so ``MARKDOWNX_MARKDOWNIFY_FUNCTION`` (which expects a
    string) works unchanged, while ``Post.content_html``/``Post.toc`` can read
    the structured attributes.
    """

    def __new__(cls, html, toc):
        obj = super().__new__(cls, html)
        obj.html = html
        obj.toc = toc
        return obj


def render_markdown(text):
    md = markdown.Markdown(
        extensions=[
            CodeChromeExtension(),
            TocExtension(baselevel=2, permalink=False),
        ],
        output_format='html5',
    )
    html = md.convert(text or '')
    return RenderedContent(html, getattr(md, 'toc', ''))
