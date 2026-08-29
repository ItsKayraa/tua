KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while",
}

# "enum" and "type" arent reservd
SOFT_KEYWORDS = {"enum", "type"}

SYMBOLS = [
    "...", "..", ".", "::", ":", "==", "~=", "<=", ">=", "<<", ">>",
    "//", "<", ">", "=", "(", ")", "{", "}", "[", "]", ";", ",",
    "+", "-", "*", "/", "%", "^", "#", "&", "~", "|", "?",
]

class TuaSyntaxError(Exception):
    def __init__(self, message, line, column=None, filename=None):
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename or "<tua>"
        loc = f"{self.filename}:{line}" + (f":{column}" if column else "")
        super().__init__(f"{loc}: {message}")


class Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r}, line={self.line})"

    def is_kw(self, *words):
        return self.kind == "KEYWORD" and self.value in words

    def is_sym(self, *syms):
        return self.kind == "SYMBOL" and self.value in syms

    def is_name(self, *names):
        return self.kind == "NAME" and (not names or self.value in names)


def tokenize(src, filename="<tua>"):
    tokens = []
    i = 0
    n = len(src)
    line = 1
    col = 1

    def advance(k=1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and src[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    def peek(offset=0):
        j = i + offset
        return src[j] if j < n else ""

    while i < n:
        c = src[i]

        if c in " \t\r\n":
            advance()
            continue

        # comments: # or #*
        if c == "-" and peek(1) == "-":
            start_line = line
            advance(2)
            if peek() == "[":
                level, ok = _long_bracket_level(src, i)
                if ok:
                    _, i2, line2 = _read_long_bracket(src, i, level, line)
                    line = line2
                    i = i2
                    col = 1
                    continue
            # line comment
            while i < n and src[i] != "\n":
                advance()
            continue

        # long strings """"""
        if c == "[" and (peek(1) == "[" or peek(1) == "="):
            level, ok = _long_bracket_level(src, i)
            if ok:
                text, i2, line2 = _read_long_bracket(src, i, level, line)
                tokens.append(Token("STRING", text, line, col))
                line = line2
                i = i2
                col = 1
                continue

        # strings
        if c == '"' or c == "'":
            quote = c
            start_line = line
            j = i + 1
            buf = []
            while j < n and src[j] != quote:
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j])
                    buf.append(src[j + 1])
                    j += 2
                    continue
                if src[j] == "\n":
                    raise TuaSyntaxError("unterminated string literal", start_line, filename=filename)
                buf.append(src[j])
                j += 1
            if j >= n:
                raise TuaSyntaxError("unterminated string literal", start_line, filename=filename)
            raw = src[i:j + 1]
            tokens.append(Token("STRING", raw, start_line, col))
            advance(j + 1 - i)
            continue

        # numbers
        if c.isdigit() or (c == "." and peek(1).isdigit()):
            j = i
            is_hex = False
            if src[j] == "0" and j + 1 < n and src[j + 1] in "xX":
                is_hex = True
                j += 2
                while j < n and (src[j] in "0123456789abcdefABCDEF.pP" or
                                  (src[j] in "+-" and src[j - 1] in "pP")):
                    j += 1
            else:
                while j < n and (src[j].isdigit() or src[j] in ".eE" or
                                  (src[j] in "+-" and j > i and src[j - 1] in "eE")):
                    j += 1
            tokens.append(Token("NUMBER", src[i:j], line, col))
            advance(j - i)
            continue

        # names / keywords
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            kind = "KEYWORD" if word in KEYWORDS else "NAME"
            tokens.append(Token(kind, word, line, col))
            advance(j - i)
            continue

        # symbols
        matched = False
        for sym in SYMBOLS:
            if src.startswith(sym, i):
                tokens.append(Token("SYMBOL", sym, line, col))
                advance(len(sym))
                matched = True
                break
        if matched:
            continue

        raise TuaSyntaxError(f"unexpected character {c!r}", line, col, filename)

    tokens.append(Token("EOF", "", line, col))
    return tokens


def _long_bracket_level(src, i):
    j = i + 1
    level = 0
    while j < len(src) and src[j] == "=":
        level += 1
        j += 1
    if j < len(src) and src[j] == "[":
        return level, True
    return 0, False


def _read_long_bracket(src, i, level, line):
    close = "]" + ("=" * level) + "]"
    start = i + level + 2
    if start < len(src) and src[start] == "\n":
        start += 1
        line += 1
    end = src.find(close, start)
    if end == -1:
        raise TuaSyntaxError("unterminated long bracket", line)
    text = src[i:end + len(close)]
    new_line = line + text.count("\n")
    return text, end + len(close), new_line