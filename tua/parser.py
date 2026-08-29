from .lexer import tokenize, Token, TuaSyntaxError
from . import ast_nodes as A

BIN_PRECEDENCE = {
    "or": (1, 1), "and": (2, 2),
    "<": (3, 3), ">": (3, 3), "<=": (3, 3), ">=": (3, 3), "~=": (3, 3), "==": (3, 3),
    "|": (4, 4), "~": (5, 5), "&": (6, 6),
    "<<": (7, 7), ">>": (7, 7),
    "..": (9, 8),
    "+": (10, 10), "-": (10, 10),
    "*": (11, 11), "/": (11, 11), "//": (11, 11), "%": (11, 11),
    "^": (14, 13),
}
UNARY_PRECEDENCE = 12

BLOCK_END = {"end", "else", "elseif", "until"}


class Parser:
    def __init__(self, tokens, filename="<tua>"):
        self.toks = tokens
        self.pos = 0
        self.filename = filename

    def cur(self):
        return self.toks[self.pos]

    def at_end(self):
        return self.cur().kind == "EOF"

    def advance(self):
        t = self.toks[self.pos]
        if t.kind != "EOF":
            self.pos += 1
        return t

    def check_sym(self, *syms):
        return self.cur().is_sym(*syms)

    def check_kw(self, *words):
        return self.cur().is_kw(*words)

    def accept_sym(self, sym):
        if self.check_sym(sym):
            return self.advance()
        return None

    def accept_kw(self, word):
        if self.check_kw(word):
            return self.advance()
        return None

    def expect_sym(self, sym):
        if not self.check_sym(sym):
            self.error(f"expected {sym!r}, got {self._describe(self.cur())}")
        return self.advance()

    def expect_kw(self, word):
        if not self.check_kw(word):
            self.error(f"expected {word!r}, got {self._describe(self.cur())}")
        return self.advance()

    def expect_name(self):
        if self.cur().kind != "NAME":
            self.error(f"expected a name, got {self._describe(self.cur())}")
        return self.advance().value

    def _describe(self, tok):
        if tok.kind == "EOF":
            return "end of file"
        return repr(tok.value)

    def error(self, message):
        raise TuaSyntaxError(message, self.cur().line, self.cur().col, self.filename)

    def parse_chunk(self):
        block = self.parse_block()
        if not self.at_end():
            self.error(f"unexpected {self._describe(self.cur())}")
        return block

    def parse_block(self):
        line = self.cur().line
        stmts = []
        while not self._block_ended():
            if self.check_sym(";"):
                self.advance()
                continue
            if self.check_kw("return"):
                stmts.append(self.parse_return())
                break
            stmts.append(self.parse_statement())
        return A.Block(stmts=stmts, line=line)

    def _block_ended(self):
        t = self.cur()
        if t.kind == "EOF":
            return True
        if t.kind == "KEYWORD" and t.value in BLOCK_END:
            return True
        return False

    def parse_statement(self):
        t = self.cur()

        if t.is_kw("if"):
            return self.parse_if()
        if t.is_kw("while"):
            return self.parse_while()
        if t.is_kw("do"):
            return self.parse_do()
        if t.is_kw("for"):
            return self.parse_for()
        if t.is_kw("repeat"):
            return self.parse_repeat()
        if t.is_kw("function"):
            return self.parse_function_stmt()
        if t.is_kw("local"):
            return self.parse_local()
        if t.is_kw("break"):
            self.advance()
            return A.BreakStmt(line=t.line)
        if t.is_kw("goto"):
            self.advance()
            name = self.expect_name()
            return A.GotoStmt(name=name, line=t.line)
        if t.is_sym("::"):
            self.advance()
            name = self.expect_name()
            self.expect_sym("::")
            return A.LabelStmt(name=name, line=t.line)

        if t.is_name("enum") and self._peek_is_enum_decl():
            return self.parse_enum()
        if t.is_name("type") and self._peek_is_type_decl():
            return self.parse_type_decl()

        return self.parse_expr_statement()

    def _peek_is_enum_decl(self):
        # enum NAME '{'
        nxt = self.toks[self.pos + 1] if self.pos + 1 < len(self.toks) else None
        nxt2 = self.toks[self.pos + 2] if self.pos + 2 < len(self.toks) else None
        return nxt is not None and nxt.kind == "NAME" and nxt2 is not None and nxt2.is_sym("{")

    def _peek_is_type_decl(self):
        return self._peek_is_enum_decl()

    def parse_if(self):
        line = self.advance().line  # 'if'
        clauses = []
        cond = self.parse_expr()
        self.expect_kw("then")
        body = self.parse_block()
        clauses.append((cond, body))
        while self.check_kw("elseif"):
            self.advance()
            c = self.parse_expr()
            self.expect_kw("then")
            b = self.parse_block()
            clauses.append((c, b))
        else_block = None
        if self.check_kw("else"):
            self.advance()
            else_block = self.parse_block()
        self.expect_kw("end")
        return A.IfStmt(clauses=clauses, else_block=else_block, line=line)

    def parse_while(self):
        line = self.advance().line
        cond = self.parse_expr()
        self.expect_kw("do")
        body = self.parse_block()
        self.expect_kw("end")
        return A.WhileStmt(cond=cond, body=body, line=line)

    def parse_do(self):
        line = self.advance().line
        body = self.parse_block()
        self.expect_kw("end")
        return A.DoStmt(body=body, line=line)

    def parse_repeat(self):
        line = self.advance().line
        body = self.parse_block()
        self.expect_kw("until")
        cond = self.parse_expr()
        return A.RepeatStmt(body=body, cond=cond, line=line)

    def parse_for(self):
        line = self.advance().line
        first_name = self.expect_name()
        if self.check_sym("="):
            self.advance()
            start = self.parse_expr()
            self.expect_sym(",")
            stop = self.parse_expr()
            step = None
            if self.accept_sym(","):
                step = self.parse_expr()
            self.expect_kw("do")
            body = self.parse_block()
            self.expect_kw("end")
            return A.NumericForStmt(var=first_name, start=start, stop=stop, step=step,
                                     body=body, line=line)
        names = [first_name]
        while self.accept_sym(","):
            names.append(self.expect_name())
        self.expect_kw("in")
        exprs = self.parse_exprlist()
        self.expect_kw("do")
        body = self.parse_block()
        self.expect_kw("end")
        return A.GenericForStmt(names=names, exprs=exprs, body=body, line=line)

    def parse_function_stmt(self):
        line = self.advance().line  # 'function'
        path = [self.expect_name()]
        while self.accept_sym("."):
            path.append(self.expect_name())
        is_method = False
        if self.accept_sym(":"):
            path.append(self.expect_name())
            is_method = True
        func = self.parse_function_body(line, implicit_self=is_method)
        return A.FunctionStmt(name_path=path, is_method=is_method, func=func, line=line)

    def parse_local(self):
        line = self.advance().line  # 'local'
        if self.check_kw("function"):
            self.advance()
            name = self.expect_name()
            func = self.parse_function_body(line, implicit_self=False)
            return A.LocalFunctionStmt(name=name, func=func, line=line)

        names, types, attribs = [], [], []
        names.append(self.expect_name())
        types.append(self.parse_optional_type_annotation())
        attribs.append(self.parse_optional_attrib())
        while self.accept_sym(","):
            names.append(self.expect_name())
            types.append(self.parse_optional_type_annotation())
            attribs.append(self.parse_optional_attrib())

        exprs = []
        if self.accept_sym("="):
            exprs = self.parse_exprlist()
        return A.LocalStmt(names=names, types=types, attribs=attribs, exprs=exprs, line=line)

    def parse_optional_type_annotation(self):
        if self.accept_sym(":"):
            return self.parse_type_expr()
        return None

    def parse_optional_attrib(self):
        # local x <const> = 1
        if self.accept_sym("<"):
            name = self.expect_name()
            self.expect_sym(">")
            return name
        return None

    def parse_return(self):
        line = self.advance().line  # 'return'
        exprs = []
        if not self._block_ended() and not self.check_sym(";"):
            exprs = self.parse_exprlist()
        self.accept_sym(";")
        return A.ReturnStmt(exprs=exprs, line=line)

    def parse_enum(self):
        line = self.advance().line  # 'enum'
        name = self.expect_name()
        self.expect_sym("{")
        members = []
        while not self.check_sym("}"):
            mname = self.expect_name()
            value = None
            if self.accept_sym("="):
                value = self.parse_expr()
            members.append((mname, value))
            if not self.accept_sym(","):
                break
        self.expect_sym("}")
        return A.EnumStmt(name=name, members=members, line=line)

    def parse_type_decl(self):
        line = self.advance().line
        name = self.expect_name()
        self.expect_sym("{")
        fields = []
        while not self.check_sym("}"):
            fname = self.expect_name()
            optional = bool(self.accept_sym("?"))
            self.expect_sym(":")
            ftype = self.parse_type_expr()
            if ftype.optional:
                optional = True
            fields.append((fname, ftype, optional))
            if not self.accept_sym(",") and not self.accept_sym(";"):
                break
        self.expect_sym("}")
        return A.TypeDeclStmt(name=name, fields=fields, line=line)

    def parse_expr_statement(self):
        line = self.cur().line
        expr = self.parse_suffixed_expr()
        if isinstance(expr, (A.CallExpr, A.MethodCallExpr)) and not self.check_sym(",", "="):
            return A.CallStmt(expr=expr, line=line)
        targets = [expr]
        while self.accept_sym(","):
            targets.append(self.parse_suffixed_expr())
        self.expect_sym("=")
        values = self.parse_exprlist()
        for tgt in targets:
            if not isinstance(tgt, (A.NameExpr, A.IndexExpr)):
                self.error("cannot assign to this expression")
        return A.AssignStmt(targets=targets, values=values, line=line)

    def parse_type_expr(self):
        line = self.cur().line
        parts = [self.parse_atom_type()]
        while self.accept_sym("|"):
            parts.append(self.parse_atom_type())
        if len(parts) == 1:
            return parts[0]
        return A.TypeExpr(kind="union", options=parts, optional=False, line=line)

    # expressions
    def parse_atom_type(self):
        line = self.cur().line
        if self.accept_sym("("):
            inner = self.parse_type_expr()
            self.expect_sym(")")
            return self._with_optional_suffix(inner)

        if self.check_sym("{"):
            return self._with_optional_suffix(self.parse_table_type())

        if self.check_kw("nil"):
            self.advance()
            base = "nil"
        else:
            base = self.expect_name()
            while self.accept_sym("."):
                base += "." + self.expect_name()
        node = A.TypeExpr(kind="named", name=base, optional=False, line=line)
        return self._with_optional_suffix(node)

    def _with_optional_suffix(self, node):
        if self.accept_sym("?"):
            node.optional = True
        return node

    def parse_table_type(self):
        # tbl typesa
        line = self.expect_sym("{").line
        if self.accept_sym("}"):
            return A.TypeExpr(kind="table", form="generic", optional=False, line=line)
        if self.check_sym("["):
            self.advance()
            key_type = self.parse_type_expr()
            self.expect_sym("]")
            self.expect_sym(":")
            value_type = self.parse_type_expr()
            self.expect_sym("}")
            return A.TypeExpr(kind="table", form="map", key=key_type, value=value_type,
                               optional=False, line=line)
        element_type = self.parse_type_expr()
        self.expect_sym("}")
        return A.TypeExpr(kind="table", form="array", element=element_type,
                           optional=False, line=line)

    def parse_function_body(self, line, implicit_self):
        self.expect_sym("(")
        params, ptypes, vararg = [], [], False
        if implicit_self:
            params.append("self")
            ptypes.append(None)
        if not self.check_sym(")"):
            while True:
                if self.check_sym("..."):
                    self.advance()
                    vararg = True
                    if self.accept_sym(":"):
                        self.parse_type_expr()
                    break
                pname = self.expect_name()
                ptype = self.parse_optional_type_annotation()
                params.append(pname)
                ptypes.append(ptype)
                if not self.accept_sym(","):
                    break
        self.expect_sym(")")
        ret_type = None
        if self.accept_sym(":"):
            ret_type = self.parse_type_expr()
        body = self.parse_block()
        self.expect_kw("end")
        return A.FunctionExpr(params=params, param_types=ptypes, vararg=vararg,
                               ret_type=ret_type, body=body, line=line)

    def parse_exprlist(self):
        exprs = [self.parse_expr()]
        while self.accept_sym(","):
            exprs.append(self.parse_expr())
        return exprs

    def parse_expr(self, min_prec=0):
        left = self.parse_unary()
        while True:
            t = self.cur()
            op = t.value if (t.kind == "SYMBOL" or t.is_kw("and", "or")) else None
            if op not in BIN_PRECEDENCE:
                break
            left_p, right_p = BIN_PRECEDENCE[op]
            if left_p < min_prec:
                break
            line = self.advance().line
            right = self.parse_expr(right_p + 1)
            left = A.BinOpExpr(op=op, left=left, right=right, line=line)
        return left

    def parse_unary(self):
        t = self.cur()
        if t.is_kw("not") or t.is_sym("-", "#", "~"):
            self.advance()
            operand = self.parse_expr(UNARY_PRECEDENCE)
            return A.UnOpExpr(op=t.value, operand=operand, line=t.line)
        return self.parse_pow()

    def parse_pow(self):
        base = self.parse_simple_expr()
        if self.check_sym("^"):
            line = self.advance().line
            exponent = self.parse_expr(BIN_PRECEDENCE["^"][1])
            return A.BinOpExpr(op="^", left=base, right=exponent, line=line)
        return base

    def parse_simple_expr(self):
        t = self.cur()
        if t.kind == "NUMBER":
            self.advance()
            return A.NumberExpr(value=t.value, line=t.line)
        if t.kind == "STRING":
            self.advance()
            return A.StringExpr(value=t.value, line=t.line)
        if t.is_kw("nil"):
            self.advance()
            return A.NilExpr(line=t.line)
        if t.is_kw("true"):
            self.advance()
            return A.TrueExpr(line=t.line)
        if t.is_kw("false"):
            self.advance()
            return A.FalseExpr(line=t.line)
        if t.is_sym("..."):
            self.advance()
            return A.VarargExpr(line=t.line)
        if t.is_kw("function"):
            self.advance()
            return self.parse_function_body(t.line, implicit_self=False)
        if t.is_sym("{"):
            return self.parse_table()
        return self.parse_suffixed_expr()

    def parse_primary_expr(self):
        t = self.cur()
        if t.is_sym("("):
            self.advance()
            inner = self.parse_expr()
            self.expect_sym(")")
            return A.ParenExpr(inner=inner, line=t.line)
        if t.kind == "NAME":
            self.advance()
            return A.NameExpr(name=t.value, line=t.line)
        self.error(f"unexpected {self._describe(t)}")

    def parse_suffixed_expr(self):
        expr = self.parse_primary_expr()
        while True:
            t = self.cur()
            if t.is_sym("."):
                self.advance()
                key = self.expect_name()
                expr = A.IndexExpr(obj=expr, key=None, dot=True, key_name=key, line=t.line)
            elif t.is_sym("["):
                self.advance()
                key = self.parse_expr()
                self.expect_sym("]")
                expr = A.IndexExpr(obj=expr, key=key, dot=False, key_name=None, line=t.line)
            elif t.is_sym(":"):
                self.advance()
                method = self.expect_name()
                args = self.parse_args()
                expr = A.MethodCallExpr(obj=expr, method=method, args=args, line=t.line)
            elif t.is_sym("(") or t.is_sym("{") or t.kind == "STRING":
                args = self.parse_args()
                expr = A.CallExpr(func=expr, args=args, line=t.line)
            else:
                break
        return expr

    def parse_args(self):
        t = self.cur()
        if t.kind == "STRING":
            self.advance()
            return [A.StringExpr(value=t.value, line=t.line)]
        if t.is_sym("{"):
            return [self.parse_table()]
        self.expect_sym("(")
        args = []
        if not self.check_sym(")"):
            args = self.parse_exprlist()
        self.expect_sym(")")
        return args

    def parse_table(self):
        line = self.expect_sym("{").line
        fields = []
        while not self.check_sym("}"):
            if self.check_sym("["):
                self.advance()
                key = self.parse_expr()
                self.expect_sym("]")
                self.expect_sym("=")
                val = self.parse_expr()
                fields.append(("expr", key, val))
            elif self.cur().kind == "NAME" and self.toks[self.pos + 1].is_sym("="):
                key = self.advance().value
                self.advance()  # '='
                val = self.parse_expr()
                fields.append(("name", key, val))
            else:
                val = self.parse_expr()
                fields.append(("pos", None, val))
            if not (self.accept_sym(",") or self.accept_sym(";")):
                break
        self.expect_sym("}")
        return A.TableExpr(fields=fields, line=line)


def parse(source, filename="<tua>"):
    tokens = tokenize(source, filename)
    return Parser(tokens, filename).parse_chunk()
