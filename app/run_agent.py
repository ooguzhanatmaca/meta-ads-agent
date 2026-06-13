import asyncio

from dotenv import load_dotenv

from app.agent.meta_ads_agent import meta_ads_agent
from app.agent.model_fallback import run_with_fallback


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
            run = await run_with_fallback(meta_ads_agent, user_message)

            if run.provider != "openai":
                print(f"(OpenAI kotası dolu — {run.provider} ile yanıtlanıyor.)")

            print(f"\nMeta Ads Agent:\n{run.result.final_output}\n")

        except Exception as error:
            print(f"\nHata oluştu: {error}\n")


if __name__ == "__main__":
    asyncio.run(main())
