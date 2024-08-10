import pytest
from marshmallowqa.cookie import retrieve_cookies


@pytest.mark.benchmark(group="cookie", min_rounds=10)
def benchmark_retrieve_cookies(benchmark):
    benchmark(retrieve_cookies, "marshmallow-qa.com", True)


def test_retrieve_cookies():
    cookies = retrieve_cookies("marshmallow-qa.com")
    assert cookies


def test_retrieve_cookies_concurrent():
    cookies = retrieve_cookies("marshmallow-qa.com", True)
    assert cookies
