class Node:
    def __init__(self, **fields):
        self.__dict__.update(fields)
        if "line" not in self.__dict__:
            self.line = 0

    def __repr__(self):
        cls = self.__class__.__name__
        fields = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if k != "line")
        return f"{cls}({fields})"

class TypeExpr(Node):
    pass

class Block(Node):
    pass


class LocalStmt(Node):
    pass


class LocalFunctionStmt(Node):
    pass


class FunctionStmt(Node):
    pass


class AssignStmt(Node):
    pass


class CallStmt(Node):
    pass


class DoStmt(Node):
    pass


class WhileStmt(Node):
    pass


class RepeatStmt(Node):
    pass


class IfStmt(Node):
    pass


class NumericForStmt(Node):
    pass


class GenericForStmt(Node):
    pass


class ReturnStmt(Node):
    pass


class BreakStmt(Node):
    pass


class GotoStmt(Node):
    pass


class LabelStmt(Node):
    pass


class EnumStmt(Node):
    pass


class TypeDeclStmt(Node):
    pass

class NilExpr(Node):
    pass


class TrueExpr(Node):
    pass


class FalseExpr(Node):
    pass


class VarargExpr(Node):
    pass


class NumberExpr(Node):
    pass


class StringExpr(Node):
    pass


class NameExpr(Node):
    pass


class IndexExpr(Node):
    pass


class CallExpr(Node):
    pass


class MethodCallExpr(Node):
    pass


class FunctionExpr(Node):
    pass


class TableExpr(Node):
    pass


class BinOpExpr(Node):
    pass


class UnOpExpr(Node):
    pass


class ParenExpr(Node):
    pass
