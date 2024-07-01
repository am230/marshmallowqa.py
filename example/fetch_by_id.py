import asyncio

from marshmallowqa import MarshmallowSession, retrieve_cookies


async def main():
    cookies = retrieve_cookies(domain="marshmallow-qa.com")
    session = await MarshmallowSession.from_cookies(
        cookies=cookies["edge"],
    )
    message = await session.fetch_message_by_id("dd923763-65c8-4cdb-b354-b21115f0cd9b")
    print(message)


if __name__ == "__main__":
    asyncio.run(main())
