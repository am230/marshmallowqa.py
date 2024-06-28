import asyncio

from marshmallowqa import Marshmallow, retrieve_cookies


async def main():
    cookies = retrieve_cookies(domain="marshmallow-qa.com")
    marshmallow = await Marshmallow.from_cookies(
        cookies=cookies["edge"],
    )
    user = await marshmallow.fetch_user()
    print(user)


if __name__ == "__main__":
    asyncio.run(main())
