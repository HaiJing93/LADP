import ast
import contextlib
import io


def execute_python_code(code: str) -> str:
    """Execute arbitrary *code* and return stdout and/or the last expression."""
    buf = io.StringIO()
    ns: dict = {}
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
