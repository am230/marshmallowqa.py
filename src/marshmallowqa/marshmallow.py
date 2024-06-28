from __future__ import annotations

import bs4
from aiohttp import ClientSession, FormData
from pydantic import BaseModel

from .cookie import MarshmallowCookie

BASE_HEADERS = {
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "user-agent": "am230/marshmallow.py (https://github.com/am230/marshmallow.py)",
}


class User(BaseModel):
    name: str
    screen_name: str
    image: str

    @property
    def url(self) -> str:
        return f"https://marshmallow-qa.com/{self.name}"


class Marshmallow:
    def __init__(
        self,
        client: ClientSession,
        cookies: MarshmallowCookie,
        scrf_token: str,
    ) -> None:
        self.client = client
        self.cookies = cookies
        self.csrf_token = scrf_token

    @classmethod
    async def from_cookies(
        cls,
        cookies: MarshmallowCookie,
        client: ClientSession | None = None,
    ) -> Marshmallow:
        client = client or ClientSession()
        response = await client.get(
            "https://marshmallow-qa.com/messages",
            cookies=cookies.model_dump(by_alias=True),
            headers=BASE_HEADERS,
        )
        response.raise_for_status()
        soup = bs4.BeautifulSoup(await response.text(), "html.parser")
        csrf_token = soup.select_one('meta[name="csrf-token"]')
        if csrf_token is None:
            raise ValueError("CSRF token not found")

        return cls(
            client=client,
            cookies=cookies,
            scrf_token=csrf_token.attrs["content"],
        )

    async def close(self) -> None:
        await self.client.close()

    async def fetch_user(self) -> User:
        response = await self.client.get(
            "https://marshmallow-qa.com/",
            cookies=self.cookies.model_dump(by_alias=True),
            headers=BASE_HEADERS,
        )
        response.raise_for_status()
        user_id = response.url.path.split("/")[1]
        response = await self.client.get(
            "https://marshmallow-qa.com/settings/profile",
            cookies=self.cookies.model_dump(by_alias=True),
            headers=BASE_HEADERS,
        )
        response.raise_for_status()
        soup = bs4.BeautifulSoup(await response.text(), "html.parser")
        form = soup.select_one('form[id^="edit_user"]')
        if form is None:
            raise ValueError("Form not found")
        name_input = form.select_one('input[id="user_nickname"][name="user[nickname]"]')
        if name_input is None:
            raise ValueError("Name input not found")
        screen_name = name_input.attrs["value"]
        image = form.select_one("picture > img")
        if image is None:
            raise ValueError("Image not found")
        user = User(
            name=user_id,
            screen_name=screen_name,
            image=image.attrs["src"],
        )
        return user

    async def fetch_messages(self) -> list[Message]:
        response = await self.client.get(
            "https://marshmallow-qa.com/messages",
            cookies=self.cookies.model_dump(by_alias=True),
            headers=BASE_HEADERS,
        )
        response.raise_for_status()
        soup = bs4.BeautifulSoup(await response.text(), "html.parser")
        messages: list[Message] = []
        for item in soup.select(
            "#messages > li[data-obscene-word-raw-content-path-value]"
        ):
            message = self._parse_message_data(item)
            messages.append(message)
        return messages

    def _parse_message_data(self, item: bs4.Tag) -> Message:
        message_id = self._parse_message_id(
            item.attrs["data-obscene-word-raw-content-path-value"]
        )
        form = item.select_one('form[action$="/like"]')
        if form is None:
            raise ValueError("Form not found")
        method_input = form.select_one('input[name="_method"]')
        liked = method_input is not None and method_input.attrs["value"] == "delete"
        token_input = form.select_one('input[name="authenticity_token"]')
        if token_input is None:
            raise ValueError("Authenticity token not found")
        authenticity_token = token_input.attrs["value"]
        content_link = item.select_one('a[data-obscene-word-target="content"]')
        if content_link is None:
            raise ValueError("Link not found")
        content = content_link.text
        message = Message(
            message_id=message_id,
            liked=liked,
            content=content,
            like_token=authenticity_token,
        )
        return message

    def _parse_message_id(self, url: str) -> str:
        parts = url.split("/")
        if len(parts) < 2:
            raise ValueError("Invalid URL")
        if parts[0] == "":
            parts.pop(0)
        if parts[0] in {"messages"}:
            parts.pop(0)
        if len(parts) == 0:
            raise ValueError("Invalid URL")
        return parts[0]


class Message(BaseModel):
    message_id: str
    liked: bool
    content: str
    like_token: str

    @property
    def image(self) -> str:
        return f"https://media.marshmallow-qa.com/system/images/{self.message_id}.png"

    async def fetch_detail(self, marshmallow: Marshmallow) -> MessageDetail:
        message_detail = await MessageDetail.from_id(marshmallow, self.message_id)
        return message_detail

    async def like(self, marshmallow: Marshmallow) -> None:
        formdata = FormData()
        formdata.add_field("_method", "delete")
        formdata.add_field(
            "authenticity_token",
            self.like_token,
        )
        response = await marshmallow.client.post(
            f"https://marshmallow-qa.com/messages/{self.message_id}/like",
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            data=formdata,
            headers={
                **BASE_HEADERS,
                "x-csrf-token": marshmallow.csrf_token,
            },
        )
        response.raise_for_status()

    async def dislike(self, marshmallow: Marshmallow) -> None:
        formdata = FormData()
        formdata.add_field("_method", "delete")
        formdata.add_field(
            "authenticity_token",
            self.like_token,
        )
        response = await marshmallow.client.post(
            f"https://marshmallow-qa.com/messages/{self.message_id}/like",
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            data=formdata,
            headers={
                **BASE_HEADERS,
                "x-csrf-token": marshmallow.csrf_token,
            },
        )
        response.raise_for_status()


class MessageDetail(Message):
    reply_token: str | None
    replied: bool

    async def block(self, marshmallow: Marshmallow) -> None:
        block = await marshmallow.client.get(
            f"https://marshmallow-qa.com/messages/{self.message_id}/block/new",
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            headers=BASE_HEADERS,
        )
        block.raise_for_status()
        soup = bs4.BeautifulSoup(await block.text(), "html.parser")
        form = soup.select_one("#new_message_block_form")
        if form is None:
            raise ValueError("Form not found")
        token_input = form.select_one('input[name="authenticity_token"]')
        if token_input is None:
            raise ValueError("Authenticity token not found")
        authenticity_token = token_input.attrs["value"]
        formdata = FormData()
        formdata.add_field("authenticity_token", authenticity_token)
        response = await marshmallow.client.post(
            f"https://marshmallow-qa.com/messages/{self.message_id}/block",
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            data=formdata,
            headers={
                **BASE_HEADERS,
                "x-csrf-token": marshmallow.csrf_token,
            },
        )
        response.raise_for_status()

    async def reply(self, marshmallow: Marshmallow, content: str) -> None:
        formdata = FormData()
        formdata.add_field("authenticity_token", self.reply_token)
        formdata.add_field("answer[message_uuid]", self.message_id)
        formdata.add_field("answer[content]", content)
        formdata.add_field("answer[skip_tweet_confirmation]", "on")
        formdata.add_field("destination", "the_others")
        formdata.add_field("answer[publish_method]", "clipboard")
        response = await marshmallow.client.post(
            f"https://marshmallow-qa.com/messages/{self.message_id}/answers",
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            data=formdata,
            headers={
                **BASE_HEADERS,
                "x-csrf-token": marshmallow.csrf_token,
            },
        )
        response.raise_for_status()

    @classmethod
    async def from_id(cls, marshmallow: Marshmallow, message_id: str) -> MessageDetail:
        url = f"https://marshmallow-qa.com/messages/{message_id}"
        response = await marshmallow.client.get(
            url,
            cookies=marshmallow.cookies.model_dump(by_alias=True),
            headers=BASE_HEADERS,
        )
        response.raise_for_status()
        soup = bs4.BeautifulSoup(await response.text(), "html.parser")
        card = soup.select_one(".card")
        if card is None:
            raise ValueError("Card not found")
        content = card.select_one('[data-obscene-word-target="content"]')
        if content is None:
            raise ValueError("Content not found")
        card_content = content.text
        form = card.select_one('form[action$="/like"]')
        if form is None:
            raise ValueError("Form not found")
        method_input = form.select_one('input[name="_method"]')
        liked = method_input is not None and method_input.attrs["value"] == "delete"
        token_input = form.select_one('input[name="authenticity_token"]')
        if token_input is None:
            raise ValueError("Authenticity token not found")
        like_token = token_input.attrs["value"]
        answer_form = card.select_one("#new_answer")
        if answer_form is None:
            reply_token = None
        else:
            token_input = answer_form.select_one('input[name="authenticity_token"]')
            if token_input is None:
                raise ValueError("Authenticity token not found")
            reply_token = token_input.attrs["value"]
        message = MessageDetail(
            message_id=message_id,
            liked=liked,
            replied=reply_token is None,
            content=card_content,
            like_token=like_token,
            reply_token=reply_token,
        )
        return message
