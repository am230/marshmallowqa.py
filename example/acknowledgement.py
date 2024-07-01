import asyncio

from marshmallowqa import MarshmallowSession, MessageDetail, retrieve_cookies


async def main():
    cookies = retrieve_cookies(domain="marshmallow-qa.com")
    session = await MarshmallowSession.from_cookies(
        cookies=cookies["edge"],
    )
    detail = await MessageDetail.from_id(
        session, "dd923763-65c8-4cdb-b354-b21115f0cd9b"
    )
    await detail.acknowledge(session)
    print(detail)


if __name__ == "__main__":
    asyncio.run(main())
