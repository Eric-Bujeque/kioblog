"""One Dark Pygments style.

Single source of truth for the syntax token colors shipped in
``kioblog/static/kioblog/code.css`` (regenerate with
``python manage.py regenerate_code_css``). The chrome of the code block
(bar, semaphore dots, copy button) is styled by the consumer project.
Hex values come from section 5 of SPEC_ericbujeque_blog.md.
"""

from pygments.style import Style
from pygments.token import (
    Comment, Error, Keyword, Name, Number, Operator, Punctuation, String, Token,
)


class OneDarkStyle(Style):
    name = 'one-dark'
    background_color = '#282c34'

    styles = {
        Token: '#abb2bf',            # base text
        Comment: 'italic #5c6370',
        Keyword: '#c678dd',
        Keyword.Constant: '#d19a66',  # True / False / None
        Keyword.Type: '#e5c07b',
        Operator: '#c678dd',
        Punctuation: '#abb2bf',
        Name: '#abb2bf',
        Name.Function: '#61afef',
        Name.Function.Magic: '#61afef',
        Name.Builtin: '#61afef',
        Name.Builtin.Pseudo: '#e06c75',
        Name.Class: '#e5c07b',
        Name.Decorator: '#61afef',
        Name.Namespace: '#e5c07b',
        Name.Tag: '#e06c75',
        Name.Attribute: '#d19a66',
        Name.Constant: '#d19a66',
        String: '#98c379',
        String.Escape: '#56b6c2',
        Number: '#d19a66',
        Error: '#e06c75',
    }
