"""TEMPORARY probe for the P2-b failure-comment verification.

Design §6.2 J7: static checks cannot prove that the e2e job posts a failure
comment on a PR. This file makes the e2e job fail once, on purpose, so the
comment can be observed, then updated on rerun.

It is deleted before PR-W2-2 is merged. Do not keep it.
"""


def test_p2b_comment_probe_fails_on_purpose():
    raise AssertionError("V4.6.0 P2-b probe: intentional failure to exercise the PR failure comment")
