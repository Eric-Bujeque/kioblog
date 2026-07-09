"""Markdown extension that renders fenced code blocks with the kioblog chrome.

The DOM structure and class names emitted here are a contract with the
consumer project (section 5 of SPEC_ericbujeque_blog.md): kioblog *emits* the
markup, the consumer only styles it. Do not rename classes or change the
structure without updating that contract.

Info-string syntax on the opening fence: ``lang`` or ``lang:path/to/file``.
Every fenced block gets the chrome; when no language is given it defaults to
``text`` and the filename span is omitted when no filename is given.
"""

import re
from html import escape

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

FENCED_BLOCK_RE = re.compile(
    r'^(?P<fence>`{3,})[ ]*(?P<info>[^\n`]*)\n'
    r'(?P<code>.*?)'
    r'(?<=\n)(?P=fence)[ ]*$',
    re.MULTILINE | re.DOTALL,
)


def _parse_info(info):
    """`python:accounts/views.py` -> ('python', 'accounts/views.py')."""
    info = info.strip()
    if not info:
        return 'text', ''
    lang, _, filename = info.partition(':')
    lang = lang.strip() or 'text'
    return lang, filename.strip()


def _gutter(code):
    lines = code.split('\n')
    return '\n'.join(str(n) for n in range(1, len(lines) + 1))


class CodeChromePreprocessor(Preprocessor):
    def run(self, lines):
        text = '\n'.join(lines)
        while True:
            m = FENCED_BLOCK_RE.search(text)
            if not m:
                break
            html = self._render_block(m.group('info'), m.group('code'))
            placeholder = self.md.htmlStash.store(html)
            text = '{}\n{}\n{}'.format(text[:m.start()], placeholder, text[m.end():])
        return text.split('\n')

    def _render_block(self, info, code):
        lang, filename = _parse_info(info)
        code = code.rstrip('\n')

        try:
            lexer = get_lexer_by_name(lang)
        except ClassNotFound:
            lexer = get_lexer_by_name('text')
        highlighted = highlight(
            code, lexer, HtmlFormatter(cssclass='highlight', wrapcode=True),
        ).strip()

        file_span = ''
        if filename:
            file_span = '<span class="code-block__file">{}</span>'.format(escape(filename))
        gutter = escape(_gutter(code))

        return (
            '<figure class="code-block" data-lang="{lang}">'
            '<div class="code-block__bar">'
            '<span class="code-block__dots"><i></i><i></i><i></i></span>'
            '{file_span}'
            '<span class="code-block__lang">{lang}</span>'
            '<button class="code-block__copy" type="button">Copy</button>'
            '</div>'
            '<div class="code-block__body">'
            '<pre class="code-block__gutter" aria-hidden="true">{gutter}</pre>'
            '{highlighted}'
            '</div>'
            '</figure>'
        ).format(lang=escape(lang), file_span=file_span, gutter=gutter, highlighted=highlighted)


class CodeChromeExtension(Extension):
    def extendMarkdown(self, md):
        # Priority above fenced_code (25) so we own every fence.
        md.preprocessors.register(CodeChromePreprocessor(md), 'kioblog_code_chrome', 30)
