from . import ast_nodes as A

INDENT = "    "

class CodeGen:
    def __init__(self, header_comment=None):
        self.lines = []
        self.header_comment = header_comment

    def generate(self, block):
        if self.header_comment:
            self.lines.append(self.header_comment)
        self.emit_block(block, 0)
        return "\n".join(self.lines) + "\n"

    def add(self, indent, text):
        self.lines.append((INDENT * indent) + text)

    def emit_block(self, block, indent):
        for stmt in block.stmts:
            self.emit_stmt(stmt, indent)

    def emit_stmt(self, s, ind):
        method = getattr(self, f"stmt_{type(s).__name__}", None)
        if method is None:
            raise NotImplementedError(f"codegen missing for {type(s).__name__}")
        method(s, ind)

    def stmt_LocalStmt(self, s, ind):
        names = ", ".join(
            n + (f" <{a}>" if a else "") for n, a in zip(s.names, s.attribs)
        )
        if s.exprs:
            values = ", ".join(self.expr(e) for e in s.exprs)
            self.add(ind, f"local {names} = {values}")
        else:
            self.add(ind, f"local {names}")

    def stmt_LocalFunctionStmt(self, s, ind):
        params = self._params(s.func)
        self.add(ind, f"local function {s.name}({params})")
        self.emit_block(s.func.body, ind + 1)
        self.add(ind, "end")

    def stmt_FunctionStmt(self, s, ind):
        if s.is_method:
            base = s.name_path[:-1]
            path = ".".join(base[:-1] + [base[-1]]) if len(base) > 1 else base[0]
            path += ":" + s.name_path[-1]
        else:
            path = ".".join(s.name_path)
        func = s.func
        if s.is_method:
            func = A.FunctionExpr(params=func.params[1:], param_types=func.param_types[1:],
                                   vararg=func.vararg, ret_type=func.ret_type, body=func.body)
        params = self._params(func)
        self.add(ind, f"function {path}({params})")
        self.emit_block(func.body, ind + 1)
        self.add(ind, "end")

    def _params(self, func):
        params = list(func.params)
        if func.vararg:
            params.append("...")
        return ", ".join(params)

    def stmt_AssignStmt(self, s, ind):
        targets = ", ".join(self.expr(t) for t in s.targets)
        values = ", ".join(self.expr(v) for v in s.values)
        self.add(ind, f"{targets} = {values}")

    def stmt_CallStmt(self, s, ind):
        self.add(ind, self.expr(s.expr))

    def stmt_DoStmt(self, s, ind):
        self.add(ind, "do")
        self.emit_block(s.body, ind + 1)
        self.add(ind, "end")

    def stmt_WhileStmt(self, s, ind):
        self.add(ind, f"while {self.expr(s.cond)} do")
        self.emit_block(s.body, ind + 1)
        self.add(ind, "end")

    def stmt_RepeatStmt(self, s, ind):
        self.add(ind, "repeat")
        self.emit_block(s.body, ind + 1)
        self.add(ind, f"until {self.expr(s.cond)}")

    def stmt_IfStmt(self, s, ind):
        for i, (cond, body) in enumerate(s.clauses):
            kw = "if" if i == 0 else "elseif"
            self.add(ind, f"{kw} {self.expr(cond)} then")
            self.emit_block(body, ind + 1)
        if s.else_block is not None:
            self.add(ind, "else")
            self.emit_block(s.else_block, ind + 1)
        self.add(ind, "end")

    def stmt_NumericForStmt(self, s, ind):
        parts = [self.expr(s.start), self.expr(s.stop)]
        if s.step is not None:
            parts.append(self.expr(s.step))
        self.add(ind, f"for {s.var} = {', '.join(parts)} do")
        self.emit_block(s.body, ind + 1)
        self.add(ind, "end")

    def stmt_GenericForStmt(self, s, ind):
        names = ", ".join(s.names)
        exprs = ", ".join(self.expr(e) for e in s.exprs)
        self.add(ind, f"for {names} in {exprs} do")
        self.emit_block(s.body, ind + 1)
        self.add(ind, "end")

    def stmt_ReturnStmt(self, s, ind):
        if s.exprs:
            self.add(ind, f"return {', '.join(self.expr(e) for e in s.exprs)}")
        else:
            self.add(ind, "return")

    def stmt_BreakStmt(self, s, ind):
        self.add(ind, "break")

    def stmt_GotoStmt(self, s, ind):
        self.add(ind, f"goto {s.name}")

    def stmt_LabelStmt(self, s, ind):
        self.add(ind, f"::{s.name}::")

    def stmt_TypeDeclStmt(self, s, ind):
        pass

    def stmt_EnumStmt(self, s, ind):
        self.add(ind, f"local {s.name} = {{")
        for name, value in s.members:
            if value is not None:
                self.add(ind + 1, f"{name} = {self.expr(value)},")
            else:
                self.add(ind + 1, f'{name} = "{name}",')
        self.add(ind, "}")

    def expr(self, e):
        method = getattr(self, f"expr_{type(e).__name__}", None)
        if method is None:
            raise NotImplementedError(f"codegen missing for {type(e).__name__}")
        return method(e)

    def expr_NilExpr(self, e):
        return "nil"

    def expr_TrueExpr(self, e):
        return "true"

    def expr_FalseExpr(self, e):
        return "false"

    def expr_VarargExpr(self, e):
        return "..."

    def expr_NumberExpr(self, e):
        return e.value

    def expr_StringExpr(self, e):
        return e.value

    def expr_NameExpr(self, e):
        return e.name

    def expr_IndexExpr(self, e):
        obj = self.expr(e.obj)
        if e.dot:
            return f"{obj}.{e.key_name}"
        return f"{obj}[{self.expr(e.key)}]"

    def expr_CallExpr(self, e):
        args = ", ".join(self.expr(a) for a in e.args)
        return f"{self.expr(e.func)}({args})"

    def expr_MethodCallExpr(self, e):
        args = ", ".join(self.expr(a) for a in e.args)
        return f"{self.expr(e.obj)}:{e.method}({args})"

    def expr_FunctionExpr(self, e):
        params = self._params(e)
        inner = CodeGen()
        inner.emit_block(e.body, 1)
        body_text = "\n".join(inner.lines)
        return f"function({params})\n{body_text}\nend"

    # tables
    def expr_TableExpr(self, e):
        if not e.fields:
            return "{}"
        parts = []
        for kind, key, val in e.fields:
            if kind == "pos":
                parts.append(self.expr(val))
            elif kind == "name":
                parts.append(f"{key} = {self.expr(val)}")
            else:
                parts.append(f"[{self.expr(key)}] = {self.expr(val)}")
        return "{ " + ", ".join(parts) + " }"

    def expr_BinOpExpr(self, e):
        return f"{self.expr(e.left)} {e.op} {self.expr(e.right)}"

    def expr_UnOpExpr(self, e):
        sep = " " if e.op == "not" else ""
        return f"{e.op}{sep}{self.expr(e.operand)}"

    def expr_ParenExpr(self, e):
        return f"({self.expr(e.inner)})"


def generate(block, header_comment=None):
    return CodeGen(header_comment).generate(block)
