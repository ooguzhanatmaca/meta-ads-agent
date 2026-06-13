import asyncio
import logging

from dotenv import load_dotenv

from app.agent.meta_ads_agent import meta_ads_agent
from app.agent.model_fallback import run_with_fallback


load_dotenv()

# Gürültülü sağlayıcı loglarını sustur (kota hatasında SDK çirkin yığın basıyor).
logging.getLogger("openai.agents").setLevel(logging.CRITICAL)
try:
    import litellm

    litellm.suppress_debug_info = True
    logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
except Exception:  # noqa: BLE001 - litellm yoksa sorun değil
    pass


async def main() -> None:
    print("Meta Ads Agent başlatıldı.")
    print("Çıkmak için 'çık' yazabilirsin.\n")

    history: list = []  # önceki turların konuşma geçmişi

    while True:
        user_message = input("Sen: ").strip()

        if user_message.lower() in {"çık", "cik", "exit", "quit"}:
            print("Meta Ads Agent kapatıldı.")
            break

        if not user_message:
            continue

        turn_input = history + [{"role": "user", "content": user_message}]

        print("Analiz ediliyor...")
        try:
            run = await run_with_fallback(meta_ads_agent, turn_input)

            if run.provider != "openai":
                print(f"({run.model} ile yanıtlanıyor.)")

            print(f"\nMeta Ads Agent:\n{run.result.final_output}\n")
            history = run.result.to_input_list()

        except Exception as error:
            print(f"\n{error}\n")


if __name__ == "__main__":
    asyncio.run(main())
