from __future__ import annotations

import sys

import rookiepy
from pydantic import BaseModel, Field, ValidationError

BROWSERS = {
    "firefox": rookiepy.firefox,
    "brave": rookiepy.brave,
    "edge": rookiepy.edge,
    "chrome": rookiepy.chrome,
    "chromium": rookiepy.chromium,
    "opera": rookiepy.opera,
    "vivaldi": rookiepy.vivaldi,
    "opera_gx": rookiepy.opera_gx,
    "librewolf": rookiepy.librewolf,
}

if sys.platform == "win32":
    BROWSERS["internet_explorer"] = rookiepy.internet_explorer
    BROWSERS["octo_browser"] = rookiepy.octo_browser


if sys.platform == "darwin":
    BROWSERS["safari"] = rookiepy.safari


class MarshmallowCookie(BaseModel):
    bid: str | None = None
    no_web_push_promotion: str | None = None
    web_push_subscription: str | None = None
    marshmallow_session: str = Field(
        alias="_marshmallow_session", serialization_alias="_marshmallow_session"
    )

    @classmethod
    def from_cookie_list(cls, cookies: rookiepy.CookieList) -> MarshmallowCookie:
        cookies_dict = {}
        for cookie in cookies:
            cookies_dict[cookie["name"]] = cookie["value"]
        return cls.model_validate(cookies_dict)


def retrieve_cookies(domain: str) -> dict[str, MarshmallowCookie]:
    result: dict[str, MarshmallowCookie] = {}
    for browser in BROWSERS:
        try:
            cookie_list = BROWSERS[browser](domains=[domain])
            result[browser] = MarshmallowCookie.from_cookie_list(cookie_list)
        except ValidationError:
            pass
        except RuntimeError:
            pass
    return result
