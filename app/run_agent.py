import asyncio

from agents import Runner
from dotenv import load_dotenv

from app.agent.meta_ads_agent import meta_ads_agent


load_dotenv()


async def main() -> None:
    print("Meta Ads Agent başlatıldı.")
    print("Çıkmak için 'çık' yazabilirsin.\n")

    while True:
        user_message = input("Sen: ").strip()

        if user_message.lower() in {"çık", "cik", "exit", "quit"}:
            print("Meta Ads Agent kapatıldı.")
            break

        if not user_message:
            continue

        try:
            result = await Runner.run(
                meta_ads_agent,
                user_message,
            )

            print(f"\nMeta Ads Agent:\n{result.final_output}\n")

        except Exception as error:
            print(f"\nHata oluştu: {error}\n")


if __name__ == "__main__":
    asyncio.run(main())
    