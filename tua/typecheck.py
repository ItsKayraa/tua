from . import ast_nodes as A

PRIMITIVES = {"number", "string", "boolean", "nil", "table", "function", "any", "unknown"}


class TuaTypeError(Exception):
    def __init__(self, errors, filename="<tua>"):
        self.errors = errors
        self.filename = filename
        lines = [f"  {filename}:{line}: {msg}" for line, msg in errors]
        super().__init__("type check failed:\n" + "\n".join(lines))


def type_expr_to_name(t):
    """Best-effort collapse of a TypeExpr down to a readable name, used for
    error messages and simple comparisons."""
    if t is None:
        return "any"
    if t.kind == "union":
        base = " | ".join(type_expr_to_name(o) for o in t.options)
    elif t.kind == "table":
        if t.form == "generic":
            base = "{}"
        elif t.form == "array":
            base = "{" + type_expr_to_name(t.element) + "}"
        else:  # map
            base = "{[" + type_expr_to_name(t.key) + "]: " + type_expr_to_name(t.value) + "}"
    else:
        base = t.name
    if getattr(t, "optional", False) and t.kind != "union":
        base += "?"
    return base


class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}

    def declare(self, name, type_expr):
        self.vars[name] = type_expr

    def lookup(self, name):
        s = self
        while s:
            if name in s.vars:
                return s.vars[name]
            s = s.parent
        return False

    def child(self):
        return Scope(self)


class FuncSig:
    def __init__(self, param_types, min_required, vararg, ret_type):
        self.param_types = param_types
        self.min_required = min_required
        self.vararg = vararg
        self.ret_type = ret_type


class Checker:
    def __init__(self, filename="<tua>"):
        self.filename = filename
        self.errors = []
        self.enums = {} # create enums now
        self.record_types = {}
        self.funcs = {}
        self.scope = Scope()

    def err(self, line, message):
        self.errors.append((line, message))

    def check(self, block):
        self._collect_declarations(block)
        self.visit_block(block)
        if self.errors:
            raise TuaTypeError(sorted(set(self.errors)), self.filename)

    def _collect_declarations(self, block):
        """First pass: learn about every enum/type/function so forward
        references (calling a function defined later in the file) work."""
        for s in block.stmts:
            if isinstance(s, A.EnumStmt):
                self.enums[s.name] = {m for m, _ in s.members}
                self.scope.declare(s.name, None)
            elif isinstance(s, A.TypeDeclStmt):
                self.record_types[s.name] = s.fields
            elif isinstance(s, A.LocalFunctionStmt):
                self.funcs[s.name] = self._sig_of(s.func)
            elif isinstance(s, A.FunctionStmt) and not s.is_method and len(s.name_path) == 1:
                self.funcs[s.name_path[0]] = self._sig_of(s.func)

    def _sig_of(self, func):
        # a param is required excepti ts optional
        min_required = 0
        for t in func.param_types:
            if t is not None and t.optional:
                break
            min_required += 1
        return FuncSig(func.param_types, min_required, func.vararg, func.ret_type)

    def infer(self, e):
        """Return a best-effort simple type name for an expression, or
        'unknown' when we genuinely can't say (which means: don't flag it)."""
        if isinstance(e, A.NumberExpr):
            return "number"
        if isinstance(e, A.StringExpr):
            return "string"
        if isinstance(e, (A.TrueExpr, A.FalseExpr)):
            return "boolean"
        if isinstance(e, A.NilExpr):
            return "nil"
        if isinstance(e, A.TableExpr):
            return "table"
        if isinstance(e, A.FunctionExpr):
            return "function"
        if isinstance(e, A.ParenExpr):
            return self.infer(e.inner)
        if isinstance(e, A.VarargExpr):
            return "unknown"
        if isinstance(e, A.NameExpr):
            found = self.scope.lookup(e.name)
            if found is False or found is None:
                return "unknown"
            return type_expr_to_name(found)
        if isinstance(e, A.IndexExpr) and e.dot and isinstance(e.obj, A.NameExpr):
            if e.obj.name in self.enums:
                if e.key_name not in self.enums[e.obj.name]:
                    self.err(e.line, f"'{e.obj.name}' has no member '{e.key_name}'")
                return e.obj.name
            return "unknown"
        if isinstance(e, A.CallExpr) and isinstance(e.func, A.NameExpr):
            sig = self.funcs.get(e.func.name)
            if sig is None:
                return "unknown"
            self._check_call_arity(e, sig)
            return type_expr_to_name(sig.ret_type) if sig.ret_type else "unknown"
        if isinstance(e, A.UnOpExpr):
            if e.op == "not":
                return "boolean"
            if e.op in ("-", "#"):
                return "number"
            return "unknown"
        if isinstance(e, A.BinOpExpr):
            if e.op in ("+", "-", "*", "/", "//", "%", "^"):
                return "number"
            if e.op == "..":
                return "string"
            if e.op in ("==", "~=", "<", ">", "<=", ">=", "and", "or"):
                return "unknown"
            return "unknown"
        return "unknown"

    def _check_call_arity(self, call, sig):
        n = len(call.args)
        if sig.vararg:
            if n < sig.min_required:
                self.err(call.line, f"call passes {n} argument(s), expected at least {sig.min_required}")
            return
        max_args = len(sig.param_types)
        if n < sig.min_required or n > max_args:
            expected = f"{sig.min_required}" if sig.min_required == max_args else f"{sig.min_required}-{max_args}"
            self.err(call.line, f"call passes {n} argument(s), expected {expected}")

    def compatible(self, declared, actual):
        """Does an actual simple type ('number', 'string', ...) satisfy a
        declared TypeExpr? Always True when we're not sure."""
        if declared is None or actual in ("unknown", "any"):
            return True
        if declared.kind == "union":
            return any(self.compatible(o, actual) for o in declared.options)
        if declared.optional and actual == "nil":
            return True
        if declared.kind == "table":
            return actual == "table"
        name = declared.name
        if name in ("any",):
            return True
        if name == actual:
            return True
        if name in self.record_types and actual == "table":
            return True  #check_table_literal
        if name in self.enums and actual == name:
            return True
        return False

    def check_table_literal(self, type_name, table_expr):
        fields = self.record_types.get(type_name)
        if fields is None:
            return
        present = set()
        for kind, key, val in table_expr.fields:
            if kind == "name":
                present.add(key)
        required = {f for f, t, optional in fields if not optional}
        missing = required - present
        if missing:
            self.err(table_expr.line,
                     f"table literal for type '{type_name}' is missing field(s): {', '.join(sorted(missing))}")
        known = {f for f, t, optional in fields}
        extra = present - known
        if extra:
            self.err(table_expr.line,
                     f"table literal for type '{type_name}' has unknown field(s): {', '.join(sorted(extra))}")

    def visit_block(self, block, new_scope=True):
        if new_scope:
            self.scope = self.scope.child()
        for s in block.stmts:
            self.visit_stmt(s)
        if new_scope:
            self.scope = self.scope.parent

    def visit_stmt(self, s):
        method = getattr(self, f"v_{type(s).__name__}", None)
        if method:
            method(s)

    def v_LocalStmt(self, s):
        for e in s.exprs:
            self.infer(e)
        for i, name in enumerate(s.names):
            declared = s.types[i] if i < len(s.types) else None
            if declared is not None and i < len(s.exprs):
                actual = self.infer(s.exprs[i])
                if declared.kind == "named" and declared.name in self.record_types \
                        and isinstance(s.exprs[i], A.TableExpr):
                    self.check_table_literal(declared.name, s.exprs[i])
                elif not self.compatible(declared, actual):
                    self.err(s.line,
                             f"cannot assign {actual} to '{name}' (declared as {type_expr_to_name(declared)})")
            self.scope.declare(name, declared)

    def v_LocalFunctionStmt(self, s):
        self.scope.declare(s.name, None)
        self._visit_function(s.func)

    def v_FunctionStmt(self, s):
        self._visit_function(s.func)

    def _visit_function(self, func):
        self.scope = self.scope.child()
        for pname, ptype in zip(func.params, func.param_types):
            self.scope.declare(pname, ptype)
        self._current_ret = getattr(self, "_current_ret", None)
        prev_ret = getattr(self, "_ret_stack", [])
        self._ret_stack = prev_ret + [func.ret_type]
        self.visit_block(func.body, new_scope=False)
        self._ret_stack = prev_ret
        self.scope = self.scope.parent

    def v_AssignStmt(self, s):
        for v in s.values:
            self.infer(v)
        for t in s.targets:
            if isinstance(t, A.NameExpr):
                declared = self.scope.lookup(t.name)
                if declared:
                    idx = s.targets.index(t)
                    if idx < len(s.values):
                        actual = self.infer(s.values[idx])
                        if not self.compatible(declared, actual):
                            self.err(s.line,
                                     f"cannot assign {actual} to '{t.name}' (declared as {type_expr_to_name(declared)})")

    def v_CallStmt(self, s):
        if isinstance(s.expr, A.CallExpr):
            self.infer(s.expr)
        elif isinstance(s.expr, A.MethodCallExpr):
            for a in s.expr.args:
                self.infer(a)

    def v_DoStmt(self, s):
        self.visit_block(s.body)

    def v_WhileStmt(self, s):
        self.infer(s.cond)
        self.visit_block(s.body)

    def v_RepeatStmt(self, s):
        self.scope = self.scope.child()
        for st in s.body.stmts:
            self.visit_stmt(st)
        self.infer(s.cond)
        self.scope = self.scope.parent

    def v_IfStmt(self, s):
        for cond, body in s.clauses:
            self.infer(cond)
            self.visit_block(body)
        if s.else_block:
            self.visit_block(s.else_block)

    def v_NumericForStmt(self, s):
        self.infer(s.start)
        self.infer(s.stop)
        if s.step:
            self.infer(s.step)
        self.scope = self.scope.child()
        self.scope.declare(s.var, None)
        self.visit_block(s.body, new_scope=False)
        self.scope = self.scope.parent

    def v_GenericForStmt(self, s):
        for e in s.exprs:
            self.infer(e)
        self.scope = self.scope.child()
        for n in s.names:
            self.scope.declare(n, None)
        self.visit_block(s.body, new_scope=False)
        self.scope = self.scope.parent

    def v_ReturnStmt(self, s):
        for e in s.exprs:
            self.infer(e)
        ret_stack = getattr(self, "_ret_stack", [])
        if ret_stack and ret_stack[-1] is not None and len(s.exprs) == 1:
            declared = ret_stack[-1]
            actual = self.infer(s.exprs[0])
            if not self.compatible(declared, actual):
                self.err(s.line,
                         f"return type {actual} doesn't match declared return type {type_expr_to_name(declared)}")


def check(block, filename="<tua>"):
    Checker(filename).check(block)
