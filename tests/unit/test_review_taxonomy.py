"""Unit tests for the closed BREAK/VULN taxonomy."""

from __future__ import annotations

import pytest

from scripts.collaboration.review_taxonomy import BV_CATEGORIES, BV_CRITICAL, check, classify_input


def categories_for(code: str) -> set[str]:
    return {item[0] for item in check([("api.py", code)])}


def test_taxonomy_has_exactly_ten_closed_categories() -> None:
    assert [item.code for item in BV_CATEGORIES] == [
        "BREAK-1",
        "BREAK-2",
        "BREAK-3",
        "BREAK-4",
        "BREAK-5",
        "VULN-1",
        "VULN-2",
        "VULN-3",
        "VULN-4",
        "VULN-5",
    ]


def test_critical_categories_are_fixed() -> None:
    assert {"BREAK-1", "BREAK-5", "VULN-1", "VULN-4"} == BV_CRITICAL


def test_category_severity_matches_critical_set() -> None:
    assert {item.code for item in BV_CATEGORIES if item.severity == "critical"} == set(BV_CRITICAL)


def test_category_severity_values_are_closed() -> None:
    assert {item.severity for item in BV_CATEGORIES} == {"critical", "warning"}


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ([], "empty"),
        ([("README.md", "")], "empty"),
        ([("README.md", "plain documentation")], "empty"),
        ([("api.py", "@app.get('/x')\ndef x():\n    return 1")], "applicable"),
        ("api.py", "unparseable"),
        (["api.py"], "unparseable"),
        ([{"path": "api.py", "content": "@app.get('/x')"}], "unparseable"),
        ([("api.py", 42)], "unparseable"),
    ],
)
def test_classify_input_has_three_states(files: object, expected: str) -> None:
    assert classify_input(files) == expected


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\n",
        "@router.post('/x')\n",
        "@bp.route('/x')\n",
    ],
)
def test_break1_positive_route_without_handler(code: str) -> None:
    assert "BREAK-1" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    return 1\n",
        "@router.get('/x')\nasync def x():\n    return {'ok': True}\n",
        "@app.get('/x')\n@decorator\ndef x():\n    return 1\n",
    ],
)
def test_break1_negative_has_handler(code: str) -> None:
    assert "BREAK-1" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    a = 1\n    b = 2\n    c = 3\n",
        "@app.get('/x')\ndef x():\n    value = 1\n    value += 1\n    print(value)\n",
        "@app.get('/x')\ndef x():\n    first = 1\n    second = 2\n    third = 3\n    fourth = 4\n",
    ],
)
def test_break2_positive_handler_without_return(code: str) -> None:
    assert "BREAK-2" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    a = 1\n    b = 2\n    return a + b\n",
        "@app.get('/x')\ndef x():\n    yield 1\n    yield 2\n    yield 3\n",
        "@app.get('/x')\ndef x(response):\n    a = 1\n    b = 2\n    c = 3\n",
    ],
)
def test_break2_negative_return_or_streaming(code: str) -> None:
    assert "BREAK-2" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.post('/a')\ndef a(data: Body):\n    return data\n@app.post('/b')\n@require_auth\ndef b(data: Body):\n    return data\n",
        "@app.put('/a')\ndef a():\n    return 1\n@app.put('/b')\n@login_required\ndef b():\n    return 1\n",
        "@app.delete('/a')\ndef a():\n    return 1\n@app.delete('/b')\n@permission('write')\ndef b():\n    return 1\n",
    ],
)
def test_break3_positive_unguarded_peer(code: str) -> None:
    assert "BREAK-3" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.post('/a')\n@require_auth\ndef a():\n    return 1\n@app.post('/b')\n@require_auth\ndef b():\n    return 1\n",
        "@app.post('/a')\ndef a():\n    return 1\n",
        "@app.get('/a')\ndef a():\n    return 1\n@app.get('/b')\ndef b():\n    return 1\n",
    ],
)
def test_break3_negative_no_comparable_unguarded_write(code: str) -> None:
    assert "BREAK-3" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    missing_call()\n    return 1\n",
        "@app.get('/x')\ndef x():\n    another_missing()\n    return 1\n",
        "@app.get('/x')\ndef x():\n    first_missing()\n    return 1\n",
    ],
)
def test_break4_positive_undefined_call(code: str) -> None:
    assert "BREAK-4" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "def known():\n    return 1\n@app.get('/x')\ndef x():\n    known()\n    return 1\n",
        "@app.get('/x')\ndef x():\n    print('ok')\n    return 1\n",
        "@app.get('/x')\ndef x():\n    return len([1])\n",
    ],
)
def test_break4_negative_known_call(code: str) -> None:
    assert "BREAK-4" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    return 1\nredirect('/missing')\n",
        "@app.get('/x')\ndef x():\n    return 1\nrouter.push('/missing')\n",
        "@app.get('/x')\ndef x():\n    return 1\nurl_for('missing')\n",
    ],
)
def test_break5_positive_missing_navigation_target(code: str) -> None:
    assert "BREAK-5" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    return 1\nredirect('/x')\n",
        "@app.get('/x')\ndef x():\n    return 1\nredirect('https://example.com')\n",
        "@app.get('/x')\ndef x():\n    return 1\nrouter.push('#anchor')\n",
    ],
)
def test_break5_negative_existing_or_external_target(code: str) -> None:
    assert "BREAK-5" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    return session.query(User)\n",
        "@app.get('/x')\ndef x():\n    return await db.fetchall(User)\n",
        "@app.get('/x')\ndef x():\n    return query.first()\n",
    ],
)
def test_vuln1_positive_orm_return(code: str) -> None:
    assert "VULN-1" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/x')\ndef x():\n    value = session.query(User)\n    return serialize(value)\n",
        "@app.get('/x')\ndef x():\n    return user\n",
        "@app.get('/x')\ndef x():\n    return {'id': 1}\n",
    ],
)
def test_vuln1_negative_indirect_or_plain_return(code: str) -> None:
    assert "VULN-1" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.post('/x')\ndef x():\n    db.add(a)\n    db.delete(b)\n",
        "@app.post('/x')\ndef x():\n    session.update(a)\n    session.save(b)\n",
        "@app.post('/x')\ndef x():\n    db.execute(a)\n    db.add(b)\n",
    ],
)
def test_vuln2_positive_writes_without_commit(code: str) -> None:
    assert "VULN-2" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.post('/x')\ndef x():\n    db.add(a)\n    db.delete(b)\n    db.commit()\n",
        "@app.post('/x')\ndef x():\n    db.add(a)\n",
        "@app.post('/x')\ndef x():\n    with transaction():\n        db.add(a)\n        db.delete(b)\n",
    ],
)
def test_vuln2_negative_commit_or_boundary(code: str) -> None:
    assert "VULN-2" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.post('/x')\ndef x(data: Body):\n    return data\n",
        "@router.put('/x')\ndef x(payload: schema):\n    return payload\n",
        "@app.patch('/x')\ndef x(data: dict):\n    return data\n",
    ],
)
def test_vuln4_positive_body_without_validation(code: str) -> None:
    assert "VULN-4" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.post('/x')\ndef x(data: Body):\n    validate(data)\n    return data\n",
        "@app.get('/x')\ndef x(data: Body):\n    return data\n",
        "@app.post('/x')\ndef x(data: Body):\n    if not data:\n        raise HTTPException(400)\n    return data\n",
    ],
)
def test_vuln4_negative_validation_or_non_write(code: str) -> None:
    assert "VULN-4" not in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/users/a')\ndef a():\n    return 1\n@app.get('/users/b')\ndef b():\n    return 1\n@app.get('/users/c')\ndef c():\n    return 1\n@app.get('/admin/q')\ndef q():\n    return 1\n",
        "@app.get('/api/a/x')\ndef a():\n    return 1\n@app.get('/api/a/y')\ndef b():\n    return 1\n@app.get('/api/a/z')\ndef c():\n    return 1\n@app.get('/other/q')\ndef q():\n    return 1\n",
        "@app.get('/v1/a')\ndef a():\n    return 1\n@app.get('/v1/b')\ndef b():\n    return 1\n@app.get('/v1/c')\ndef c():\n    return 1\n@app.get('/other/q')\ndef q():\n    return 1\n",
    ],
)
def test_vuln5_positive_inconsistent_prefix(code: str) -> None:
    assert "VULN-5" in categories_for(code)


@pytest.mark.parametrize(
    "code",
    [
        "@app.get('/users/a')\ndef a():\n    return 1\n@app.get('/users/b')\ndef b():\n    return 1\n@app.get('/users/c')\ndef c():\n    return 1\n",
        "@app.get('/a')\ndef a():\n    return 1\n@app.get('/b')\ndef b():\n    return 1\n@app.get('/c')\ndef c():\n    return 1\n",
        "@app.get('/users/a')\ndef a():\n    return 1\n@app.get('/users/b')\ndef b():\n    return 1\n",
    ],
)
def test_vuln5_negative_consistent_or_boundary_prefix(code: str) -> None:
    assert "VULN-5" not in categories_for(code)
