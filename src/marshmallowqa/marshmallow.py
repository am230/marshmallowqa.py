from __future__ import annotations

import bs4
from aiohttp import ClientSession
from pydantic import BaseModel

from .action import Action, ActionType
from .const import BASE_HEADERS
from .cookie import MarshmallowCookie


class User(BaseModel):
    name: str
    screen_name: str
    image: str

    @property
    def url(self) -> str:
        return f"https://marshmallow-qa.com/{self.name}"


LIKE_ACTION = ActionType(
    name="like",
    selector='form[action*="/like"]',
)
REPLY_ACTION = ActionType(
    name="reply",
    selector="#new_answer",
)
ACKNOWLEDGEMENT_ACTION = ActionType(
    name="acknowledgement",
    selector='form[action*="/acknowledgement"]',
)


class MarshmallowSession:
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
    ) -> MarshmallowSession:
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

    async def fetch_message_by_id(self, message_id: str) -> Message:
        response = await self.client.get(
            f"https://marshmallow-qa.com/messages/{message_id}",
            cookies=self.cookies.model_dump(by_alias=True),
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
        like_action = LIKE_ACTION.parse(soup)
        reply_action = (
            REPLY_ACTION.parse(soup) if soup.select_one("#new_answer") else None
        )
        acknowledge_action = ACKNOWLEDGEMENT_ACTION.parse(soup)
        message = MessageDetail(
            message_id=message_id,
            like_action=like_action,
            content=card_content,
            reply_action=reply_action,
            acknowledge_action=acknowledge_action,
        )
        return message

    def _parse_message_data(self, item: bs4.Tag) -> Message:
        message_id = self._parse_message_id(
            item.attrs["data-obscene-word-raw-content-path-value"]
        )
        like_action = LIKE_ACTION.parse(item)
        acknowledge_action = ACKNOWLEDGEMENT_ACTION.parse(item)
        content_link = item.select_one('a[data-obscene-word-target="content"]')
        if content_link is None:
            raise ValueError("Link not found")
        content = content_link.text
        message = Message(
            message_id=message_id,
            content=content,
            like_action=like_action,
            acknowledge_action=acknowledge_action,
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
    content: str
    like_action: Action
    acknowledge_action: Action

    @property
    def image(self) -> str:
        return f"https://media.marshmallow-qa.com/system/images/{self.message_id}.png"

    @property
    def url(self) -> str:
        return f"https://marshmallow-qa.com/messages/{self.message_id}"

    async def fetch_detail(self, marshmallow: MarshmallowSession) -> MessageDetail:
        message_detail = await MessageDetail.from_id(marshmallow, self.message_id)
        return message_detail

    async def like(self, marshmallow: MarshmallowSession, liked: bool = True) -> None:
        await self.like_action.set(marshmallow, delete=not liked)

    @property
    def liked(self) -> bool:
        return self.like_action.delete

    async def acknowledge(
        self, marshmallow: MarshmallowSession, acknowledged: bool = True
    ) -> None:
        await self.acknowledge_action.set(marshmallow, delete=not acknowledged)

    @property
    def acknowledged(self) -> bool:
        return self.acknowledge_action.delete

    async def block(self, marshmallow: MarshmallowSession) -> None:
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
        action = Action.from_form(form)
        await action.set(marshmallow)

    async def try_edit_reply(
        self, marshmallow: MarshmallowSession, content: str
    ) -> None:
        action = Action(
            action=f"/messages/{self.message_id}/answers",
            token="",
            delete=False,
        )
        await action.set(
            marshmallow,
            data={
                "answer[message_uuid]": self.message_id,
                "answer[content]": content,
                "answer[skip_tweet_confirmation]": "on",
                "destination": "the_others",
                "answer[publish_method]": "clipboard",
            },
        )


class MessageDetail(Message):
    reply_action: Action | None

    @property
    def replied(self) -> bool:
        return self.reply_action is None

    async def reply(self, marshmallow: MarshmallowSession, content: str) -> None:
        if self.reply_action is None:
            raise ValueError("Message already replied")
        await self.reply_action.set(
            marshmallow,
            delete=False,
            data={
                "answer[message_uuid]": self.message_id,
                "answer[content]": content,
                "answer[skip_tweet_confirmation]": "on",
                "destination": "the_others",
                "answer[publish_method]": "clipboard",
            },
        )

    @classmethod
    async def from_id(
        cls, marshmallow: MarshmallowSession, message_id: str
    ) -> MessageDetail:
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
        like_action = LIKE_ACTION.parse(soup)
        reply_action = (
            REPLY_ACTION.parse(soup) if soup.select_one("#new_answer") else None
        )
        acknowledge_action = ACKNOWLEDGEMENT_ACTION.parse(soup)
        message = MessageDetail(
            message_id=message_id,
            like_action=like_action,
            content=card_content,
            reply_action=reply_action,
            acknowledge_action=acknowledge_action,
        )
        return message
