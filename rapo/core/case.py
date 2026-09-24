"""Contains case management elements."""

import re


NORMAL = 'Normal'
INFO = 'Info'
ERROR = 'Error'
WARNING = 'Warning'
INCIDENT = 'Incident'
SUCCESS = 'Success'
LOSS = 'Loss'
DISCREPANCY = 'Discrepancy'
DUPLICATE = 'Duplicate'


# Comments, quoted literals and identifiers are skipped whole, so a THEN or a
# parenthesis inside them is never read as SQL.
_TOKEN = re.compile(r"""
    (?P<skip>--[^\n]*|/\*.*?(?:\*/|\Z)|'(?:[^']|'')*'?|"[^"]*"?|\s+)
    |(?P<word>[A-Za-z_][\w$#]*)
    |(?P<number>\d+(?:\.\d*)?)
    |(?P<other>.)
""", re.VERBOSE | re.DOTALL)
_BRANCH_END = ('WHEN', 'ELSE', 'END')


def find_case_ids(statement):
    """Find the case IDs returned by a Case definition.

    A number is a case ID only when it is the whole THEN/ELSE result of a CASE
    whose value is the statement's value: the outer CASE, or a CASE that is
    itself the whole result of such a branch. A CASE nested in a WHEN
    condition or inside a function call returns ordinary values and is left
    alone.

    Returns
    -------
    spans : list of tuple
        (start, end, case_id) of each case ID, in order.
    """
    tokens = []
    for match in _TOKEN.finditer(statement or ''):
        if match.lastgroup != 'skip':
            tokens.append((match.lastgroup, match.group().upper(),
                           match.start(), match.end()))
    spans = []
    stack = []    # [kind, returns_result] of each open CASE and parenthesis
    expect = True  # whether the next token is in result position
    for i, (kind, text, start, end) in enumerate(tokens):
        top = stack[-1] if stack else None
        after = tokens[i+1] if i + 1 < len(tokens) else None
        if kind == 'number' and expect and text.isdigit():
            closes = (after is None
                      or (after[0] == 'word' and after[1] in _BRANCH_END)
                      or (after[1] == ')' and top and top[0] == '('))
            if closes:
                spans.append((start, end, int(text)))
        if text == 'CASE':
            stack.append(['CASE', expect])
        elif text == 'END' and top and top[0] == 'CASE':
            stack.pop()
        elif text == '(':
            stack.append(['(', expect])
        elif text == ')' and top and top[0] == '(':
            stack.pop()
        if text in ('THEN', 'ELSE') and top and top[0] == 'CASE':
            expect = top[1]
        elif text == '(':
            expect = stack[-1][1]
        else:
            expect = False
    return spans
