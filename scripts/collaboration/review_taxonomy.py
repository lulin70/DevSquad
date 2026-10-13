"""Deterministic BREAK/VULN review taxonomy checks."""

from __future__ import annotations

import builtins
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import NamedTuple, TypedDict


@dataclass(frozen=True)
class BVCategory:
    """Closed metadata for one BREAK/VULN category."""

    code: str
    name: str
    severity: str
    description_zh: str
    description_en: str


BV_CATEGORIES: tuple[BVCategory, ...] = (
    BVCategory("BREAK-1", "entry_point_break", "critical", "路由缺少处理函数", "route without handler"),
    BVCategory("BREAK-2", "handler_no_return", "warning", "处理函数没有返回值", "handler without return"),
    BVCategory("BREAK-3", "write_endpoint_unguarded", "warning", "写入端点缺少守卫", "unguarded write endpoint"),
    BVCategory("BREAK-4", "undefined_call", "warning", "处理函数调用未定义名称", "undefined call in handler"),
    BVCategory("BREAK-5", "navigation_target_missing", "critical", "导航目标不存在", "navigation target missing"),
    BVCategory("VULN-1", "orm_object_returned", "critical", "端点直接返回 ORM 查询对象", "ORM object returned"),
    BVCategory("VULN-2", "writes_without_commit", "warning", "写入操作缺少提交或事务", "writes without commit"),
    BVCategory("VULN-3", "endpoint_unreferenced", "warning", "端点在变更集中没有引用", "endpoint unreferenced"),
    BVCategory(
        "VULN-4",
        "write_endpoint_no_validation",
        "critical",
        "写入端点缺少输入校验",
        "write endpoint without validation",
    ),
    BVCategory("VULN-5", "route_prefix_inconsistent", "warning", "路由前缀不一致", "inconsistent route prefix"),
)

BV_CRITICAL: frozenset[str] = frozenset({"BREAK-1", "BREAK-5", "VULN-1", "VULN-4"})

_ROUTE_DECORATOR = re.compile(
    r"@\s*(?:app|router|bp|blueprint|api)\."
    r"(?P<method>get|post|put|delete|patch|route|api_route)\s*\("
    r"(?P<args>[^\n]*)",
    re.IGNORECASE,
)
_DJANGO_ROUTE = re.compile(r"(?:path|re_path)\s*\(\s*(['\"])(?P<path>[^'\"]+)\1")
_NAVIGATION = re.compile(
    r"(?:url_for|redirect|reverse)\s*\(\s*['\"](?P<target>[^'\"]+)['\"]"
    r"|router\.push\s*\(\s*['\"](?P<push>[^'\"]+)['\"]"
    r"|href\s*=\s*['\"](?P<href>/[^'\"]*)['\"]",
    re.IGNORECASE,
)
_HANDLER = re.compile(r"^\s*(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)")
_ASSIGNMENT = re.compile(r"^\s*(?P<name>[A-Za-z_]\w*)\s*=")
_CALL = re.compile(r"\b(?P<name>[A-Za-z_]\w*)\s*\(")


class _Route(NamedTuple):
    path: str
    method: str
    file_path: str
    decorator_line: int
    handler_line: int | None
    handler_name: str | None
    handler_args: str
    body: tuple[tuple[int, str], ...]
    decorator_block: tuple[str, ...]


class _Hit(NamedTuple):
    category_code: str
    rule_id: str
    line_number: int
    description: str
    file_path: str


class _Context(TypedDict):
    path: str
    content: str
    lines: list[tuple[int, str]]
    routes: list[_Route]


def classify_input(files: object) -> str:
    """Return ``applicable``, ``empty``, or ``unparseable``.

    A valid, non-empty changeset without a route/navigation object is treated
    as empty for the taxonomy. This gives documentation-only changes a real
    N/A disclosure instead of claiming that the ten rules were exercised.
    """
    if not isinstance(files, list):
        return "unparseable" if files else "empty"
    if not files:
        return "empty"

    valid: list[tuple[str, str]] = []
    for item in files:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        path, content = item
        if isinstance(path, str) and isinstance(content, str):
            valid.append((path, content))
    if not valid:
        return "unparseable"
    if not any(content.strip() for _, content in valid):
        return "empty"
    if not any(_has_taxonomy_object(content) for _, content in valid):
        return "empty"
    return "applicable"


def check(
    files: list[tuple[str, str]],
    line_scan: Callable[[str, str], Iterable[tuple[int, str]]] | None = None,
) -> list[tuple[str, str, int, str, str]]:
    """Run the ten deterministic checks and return category/rule/line/path data."""
    normalized = [(path, content) for path, content in files if isinstance(path, str) and isinstance(content, str)]
    if not normalized:
        return []
    scan = line_scan or _default_line_scan
    contexts = [_build_context(path, content, scan) for path, content in normalized]
    hits: list[_Hit] = []
    for _category, rule in _RULE_TABLE:
        for context in contexts:
            hits.extend(rule(context, contexts))
    return [(hit.category_code, hit.rule_id, hit.line_number, hit.description, hit.file_path) for hit in hits]


def _default_line_scan(_path: str, content: str) -> Iterable[tuple[int, str]]:
    return enumerate(content.splitlines(), 1)


def _has_taxonomy_object(content: str) -> bool:
    return bool(_ROUTE_DECORATOR.search(content) or _DJANGO_ROUTE.search(content) or _NAVIGATION.search(content))


def _extract_path(method: str, args: str) -> str:
    quoted = re.search(r"['\"](?P<path>[^'\"]+)['\"]", args)
    return quoted.group("path") if quoted else ""


def _route_method(method: str, args: str) -> str:
    methods = re.search(r"methods\s*=\s*\[([^]]+)\]", args, re.IGNORECASE)
    if methods:
        found = re.search(r"['\"](get|post|put|patch|delete|head)['\"]", methods.group(1), re.IGNORECASE)
        if found:
            return found.group(1).lower()
    return method.lower() if method.lower() != "route" else "get"


def _build_context(
    file_path: str,
    content: str,
    scan: Callable[[str, str], Iterable[tuple[int, str]]],
) -> _Context:
    lines = list(scan(file_path, content))
    routes: list[_Route] = []
    route_starts: list[tuple[int, str, str, str]] = []
    for number, line in lines:
        match = _ROUTE_DECORATOR.search(line)
        if match:
            path = _extract_path(match.group("method"), match.group("args"))
            if path and not match.group("args").lstrip().startswith("name="):
                route_starts.append((number, path, _route_method(match.group("method"), match.group("args")), line))
        for django in _DJANGO_ROUTE.finditer(line):
            route_starts.append((number, django.group("path"), "get", line))

    for index, (number, path, method, _decorator) in enumerate(route_starts):
        next_start = route_starts[index + 1][0] if index + 1 < len(route_starts) else len(lines) + 1
        decorator_lines = [text for line_no, text in lines if number <= line_no < next_start]
        handler_line: int | None = None
        handler_name: str | None = None
        handler_args = ""
        for line_no, text in lines:
            if number < line_no < next_start:
                handler = _HANDLER.match(text)
                if handler:
                    handler_line = line_no
                    handler_name = handler.group("name")
                    handler_args = handler.group("args")
                    break
        body: tuple[tuple[int, str], ...] = ()
        if handler_line is not None:
            body = _function_body(lines, handler_line)
        routes.append(
            _Route(
                path, method, file_path, number, handler_line, handler_name, handler_args, body, tuple(decorator_lines)
            )
        )

    return {"path": file_path, "content": content, "lines": lines, "routes": routes}


def _function_body(lines: list[tuple[int, str]], handler_line: int) -> tuple[tuple[int, str], ...]:
    def_line = next(text for number, text in lines if number == handler_line)
    indent = len(def_line) - len(def_line.lstrip())
    body: list[tuple[int, str]] = []
    started = False
    for number, text in lines:
        if number <= handler_line:
            continue
        stripped = text.strip()
        current_indent = len(text) - len(text.lstrip())
        if stripped and current_indent <= indent:
            break
        if stripped:
            started = True
        if started and stripped:
            body.append((number, text))
    return tuple(body)


def _record(context: _Context, category: str, rule_id: str, line: int, detail: str) -> _Hit:
    return _Hit(category, rule_id, line, f"{detail} ({rule_id})", context["path"])


def _check_break1(context: _Context, _all: list[_Context]) -> list[_Hit]:
    hits: list[_Hit] = []
    for route in context["routes"]:
        if route.handler_line is None:
            hits.append(
                _record(
                    context,
                    "BREAK-1",
                    "BV-BREAK1-route-without-handler",
                    route.decorator_line,
                    "route decorator has no following handler",
                )
            )
    return hits


def _check_break2(context: _Context, _all: list[_Context]) -> list[_Hit]:
    hits: list[_Hit] = []
    for route in context["routes"]:
        if route.handler_line is None or len(route.body) < 3:
            continue
        body_text = "\n".join(text for _, text in route.body)
        if "return" not in body_text and "yield" not in body_text and "response" not in route.handler_args:
            hits.append(
                _record(
                    context,
                    "BREAK-2",
                    "BV-BREAK2-handler-no-return",
                    route.handler_line,
                    "route handler has no return statement",
                )
            )
    return hits


def _is_guarded(route: _Route) -> bool:
    guard = re.compile(r"Depends\s*\(\s*get_current_user|require_auth|login_required|permission|token", re.IGNORECASE)
    return bool(guard.search("\n".join(route.decorator_block)) or guard.search(route.handler_args))


def _check_break3(context: _Context, _all: list[_Context]) -> list[_Hit]:
    routes = context["routes"]
    writes = [
        route
        for route in routes
        if route.method in {"post", "put", "patch", "delete"} and route.handler_line is not None
    ]
    if len(writes) < 2 or not any(_is_guarded(route) for route in writes):
        return []
    return [
        _record(
            context,
            "BREAK-3",
            "BV-BREAK3-write-endpoint-unguarded",
            route.handler_line or route.decorator_line,
            "write endpoint has no guard",
        )
        for route in writes
        if not _is_guarded(route)
    ]


def _known_names(context: _Context) -> set[str]:
    content = context["content"]
    names = set(dir(builtins)) | {"request", "response", "HTTPException", "JSONResponse", "Depends", "Body"}
    names.update(match.group("name") for match in _HANDLER.finditer(content))
    names.update(match.group("name") for match in _ASSIGNMENT.finditer(content))
    names.update(re.findall(r"(?:from\s+\S+\s+import|import)\s+([A-Za-z_]\w*)", content))
    return names


def _check_break4(context: _Context, _all: list[_Context]) -> list[_Hit]:
    names = _known_names(context)
    hits: list[_Hit] = []
    for route in context["routes"]:
        if route.handler_line is None:
            continue
        for line_number, text in route.body:
            for match in _CALL.finditer(text):
                name = match.group("name")
                if name not in names and name not in {"if", "for", "while", "except", "return", "print"}:
                    hits.append(
                        _record(
                            context,
                            "BREAK-4",
                            "BV-BREAK4-undefined-call-in-handler",
                            line_number,
                            f"undefined call '{name}' in route handler",
                        )
                    )
                    break
            else:
                continue
            break
    return hits


def _check_break5(context: _Context, all_contexts: list[_Context]) -> list[_Hit]:
    registered = {(route.path, route.handler_name) for item in all_contexts for route in item["routes"]}
    if not registered:
        return []
    hits: list[_Hit] = []
    for line_number, text in context["lines"]:
        for match in _NAVIGATION.finditer(text):
            target = next((value for value in match.groups() if value is not None), "")
            if target.startswith(("http://", "https://", "#")):
                continue
            if not any(target in (path, name) or target.rstrip("/") == path.rstrip("/") for path, name in registered):
                hits.append(
                    _record(
                        context,
                        "BREAK-5",
                        "BV-BREAK5-nav-target-missing",
                        line_number,
                        f"navigation target '{target}' has no route",
                    )
                )
    return hits


def _check_vuln1(context: _Context, _all: list[_Context]) -> list[_Hit]:
    pattern = re.compile(
        r"return\s+(?:await\s+)?(?:db|session|query|q)\.(?:query|all|first|get|scalar|scalars|execute|fetchall|fetchone)\s*\(",
        re.IGNORECASE,
    )
    hits: list[_Hit] = []
    for route in context["routes"]:
        for line_number, text in route.body:
            if pattern.search(text):
                hits.append(
                    _record(
                        context,
                        "VULN-1",
                        "BV-VULN1-orm-object-returned",
                        line_number,
                        "route returns an ORM query object directly",
                    )
                )
    return hits


def _check_vuln2(context: _Context, _all: list[_Context]) -> list[_Hit]:
    write = re.compile(r"\.(?:add|delete|update|save|execute)\s*\(", re.IGNORECASE)
    hits: list[_Hit] = []
    for route in context["routes"]:
        body_text = "\n".join(text for _, text in route.body)
        if len(write.findall(body_text)) >= 2 and not re.search(r"commit|transaction|atomic", body_text, re.IGNORECASE):
            hits.append(
                _record(
                    context,
                    "VULN-2",
                    "BV-VULN2-writes-without-commit",
                    route.handler_line or route.decorator_line,
                    "multiple writes have no commit or transaction",
                )
            )
    return hits


def _check_vuln3(context: _Context, _all: list[_Context]) -> list[_Hit]:
    lines = context["lines"]
    routes = context["routes"]
    hits: list[_Hit] = []
    for route in routes:
        non_registration = "\n".join(text for number, text in lines if number != route.decorator_line)
        if route.path not in non_registration:
            hits.append(
                _record(
                    context,
                    "VULN-3",
                    "BV-VULN3-endpoint-unreferenced",
                    route.decorator_line,
                    f"endpoint '{route.path}' is not referenced in the changeset",
                )
            )
    return hits


def _check_vuln4(context: _Context, _all: list[_Context]) -> list[_Hit]:
    body_hint = re.compile(r"\b(?:data|payload)\s*:|\bBody\s*\(|\bschema\b", re.IGNORECASE)
    validation = re.compile(r"validate|check_|if\s+not|raise\s+.*HTTPException\s*\(\s*4", re.IGNORECASE)
    hits: list[_Hit] = []
    for route in context["routes"]:
        if route.method not in {"post", "put", "patch", "delete"} or route.handler_line is None:
            continue
        body_text = "\n".join(text for _, text in route.body)
        if body_hint.search(route.handler_args) and not validation.search(body_text):
            hits.append(
                _record(
                    context,
                    "VULN-4",
                    "BV-VULN4-write-endpoint-no-validation",
                    route.handler_line,
                    "write endpoint accepts body data without validation",
                )
            )
    return hits


def _check_vuln5(context: _Context, _all: list[_Context]) -> list[_Hit]:
    routes = context["routes"]
    if len(routes) < 3:
        return []
    clusters: dict[str, list[_Route]] = {}
    for route in routes:
        parts = [part for part in route.path.split("/") if part]
        if len(parts) < 2:
            continue
        clusters.setdefault(parts[0], []).append(route)
    if not clusters:
        return []
    prefix, members = max(clusters.items(), key=lambda item: len(item[1]))
    if len(members) / len(routes) < 0.7 or len(members) < 2:
        return []
    health = {"health", "metrics", "ping"}
    return [
        _record(
            context,
            "VULN-5",
            "BV-VULN5-route-prefix-inconsistent",
            route.decorator_line,
            f"route prefix is outside the dominant '/{prefix}' cluster",
        )
        for route in routes
        if route not in members and route.path.strip("/").split("/")[0] not in health
    ]


_RULE_TABLE: tuple[tuple[BVCategory, Callable[[_Context, list[_Context]], list[_Hit]]], ...] = (
    (BV_CATEGORIES[0], _check_break1),
    (BV_CATEGORIES[1], _check_break2),
    (BV_CATEGORIES[2], _check_break3),
    (BV_CATEGORIES[3], _check_break4),
    (BV_CATEGORIES[4], _check_break5),
    (BV_CATEGORIES[5], _check_vuln1),
    (BV_CATEGORIES[6], _check_vuln2),
    (BV_CATEGORIES[7], _check_vuln3),
    (BV_CATEGORIES[8], _check_vuln4),
    (BV_CATEGORIES[9], _check_vuln5),
)


__all__ = ["BVCategory", "BV_CATEGORIES", "BV_CRITICAL", "classify_input", "check"]
