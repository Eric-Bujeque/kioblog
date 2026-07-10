"""Regenerate the shipped One Dark token stylesheet.

Writes ``kioblog/static/kioblog/code.css`` from
:class:`kioblog.markdown.pygments_onedark.OneDarkStyle` so the ``.highlight``
token classes always match what the renderer emits. Run after changing the
style. The file is committed and shipped with the package.
"""

from pathlib import Path

from django.core.management.base import BaseCommand
from pygments.formatters import HtmlFormatter

from kioblog.markdown.pygments_onedark import OneDarkStyle

HEADER = (
    '/* One Dark syntax token colors for kioblog code blocks.\n'
    ' * Generated from kioblog.markdown.pygments_onedark.OneDarkStyle.\n'
    ' * Regenerate with: python manage.py regenerate_code_css\n'
    ' * The code-block chrome (bar, dots, copy button) is styled by the consumer. */\n'
)


class Command(BaseCommand):
    help = 'Regenerate kioblog/static/kioblog/code.css from the OneDark Pygments style'

    def handle(self, *args, **options):
        css = HtmlFormatter(style=OneDarkStyle).get_style_defs('.highlight')
        out = Path(__file__).resolve().parents[2] / 'static' / 'kioblog' / 'code.css'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(HEADER + css + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS('Wrote {}'.format(out)))
