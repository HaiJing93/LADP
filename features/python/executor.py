"""Simple helper to execute user-supplied Python code."""

import ast
import contextlib
import io
import json
import math

import pandas as pd


def execute_python_code(code: str) -> str:
    """Execute arbitrary *code* and return stdout and/or the last expression.

    The execution environment comes with ``pandas`` imported as ``pd`` as well
    as the standard ``json`` and ``math`` modules for convenience.
    """

    buf = io.StringIO()
    ns: dict = {
        "pd": pd,
        "json": json,
        "math": math,
    }
    try:
        tree = ast.parse(code, mode="exec")
        *body, last = tree.body or [ast.Pass()]
        with contextlib.redirect_stdout(buf):
            if isinstance(last, ast.Expr):
                exec(compile(ast.Module(body=body, type_ignores=[]), "<py>", "exec"), ns, ns)
                result = eval(compile(ast.Expression(last.value), "<py>", "eval"), ns, ns)
            else:
                exec(code, ns, ns)
                result = ns.get("_")
    except Exception as exc:
        return f"Error: {exc}"

    output = buf.getvalue()
    if result is not None:
        output += str(result)
    return output.strip()
