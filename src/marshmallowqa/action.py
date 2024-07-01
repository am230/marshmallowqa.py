from __future__ import annotations

from typing import TYPE_CHECKING

import bs4
from aiohttp import FormData
from pydantic import BaseModel

from .const import BASE_HEADERS

if TYPE_CHECKING:
    from .marshmallow import MarshmallowSession


class Action(BaseModel):
    action: str
    token: str
    delete: bool

    @classmethod
    def from_form(cls, form: bs4.Tag):
        action = form.attrs["action"]
        method_input = form.select_one('input[name="_method"]')
        delete = (
            method_input is not None and method_input.attrs["value"].lower() == "delete"
        )
        token_input = form.select_one('input[name="authenticity_token"]')
        if token_input is None:
            raise ValueError("Authenticity token not found")
        token = token_input.attrs["value"]
        return cls(
            action=action,
            token=token,
            delete=delete,
        )

    async def set(
        self,
        marshmallow: MarshmallowSession,
        delete: bool = False,
        data: dict[str, str] | None = None,
    ):
        formdata = FormData()
        formdata.add_field("authenticity_token", self.token)
        if delete:
            formdata.add_field("_method", "delete")
        if data is not None:
            for key, value in data.items():
                formdata.add_field(key, value)
        response = await marshmallow.client.post(
            f"https://marshmallow-qa.com{self.action}",
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            data=formdata,
            headers={
                **BASE_HEADERS,
                "x-csrf-token": marshmallow.csrf_token,
            },
        )
        response.raise_for_status()


class ActionType:
    def __init__(
        self,
        name: str,
        selector: str,
    ):
        self.name = name
        self.selector = selector

    def parse(self, tag: bs4.Tag) -> Action:
        form = tag.select_one(self.selector)
        if form is None:
            raise ValueError(f"Form not found for {self.name}")
        return Action.from_form(form)
