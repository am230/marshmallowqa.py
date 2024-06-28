import asyncio

from marshmallow import Marshmallow, retrieve_cookies


async def main():
    cookies = retrieve_cookies(domain="marshmallow-qa.com")
    marshmallow = await Marshmallow.from_cookies(
        cookies=cookies["edge"],
    )
    messages = await marshmallow.fetch_messages()
    detail = await messages[0].fetch_detail(marshmallow)
    await detail.reply(marshmallow, "Hello!")


if __name__ == "__main__":
    asyncio.run(main())
