from .lexer import TuaSyntaxError
from .parser import parse
from .typecheck import check, TuaTypeError
from .codegen import generate

__version__ = "1.0.0"


def compile_source(source, filename="<tua>", type_check=True, header_comment=None):
    ast = parse(source, filename)
    if type_check:
        check(ast, filename)
    return generate(ast, header_comment)
