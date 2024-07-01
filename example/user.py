import asyncio

from marshmallowqa import MarshmallowSession, retrieve_cookies


async def main():
    cookies = retrieve_cookies(domain="marshmallow-qa.com")
    session = await MarshmallowSession.from_cookies(
        cookies=cookies["edge"],
    )
    user = await session.fetch_user()
    print(user)


if __name__ == "__main__":
    asyncio.run(main())
