# AGENTS.md

Bu dosya, kod tabanında çalışan yapay zekâ agent'ları ve yeni katkı sağlayanlar
için kısa bir kılavuzdur. Kullanıcıya yönelik dokümantasyon için [README.md](README.md).

## Proje

Meta (Facebook/Instagram) reklam hesabını doğal dilde analiz eden ve — operatör
modu açıkken — yöneten bir yapay zekâ danışmanı. `openai-agents` SDK üzerine kurulu;
modeller LiteLLM ile çağrılır (varsayılan Google Gemini, fallback zinciri ile).

## Komutlar

```bash
.venv/bin/python -m pytest -q              # Testler (hepsi geçmeli)
.venv/bin/python -m app.run_agent          # Agent ile sohbet (terminal)
.venv/bin/python -m app.send_report        # Günlük e-posta raporu (LLM'siz, kural tabanlı)
.venv/bin/python -m streamlit run app/dashboard.py   # Görsel panel
```

## Mimari

```
app/
├── agent/    # Agent tanımı (meta_ads_agent.py) + model fallback zinciri
├── meta/     # Meta API client + raporlar/trend/anomali/simülasyon/görsel + history (saf mantık)
├── rules/    # Performans, kreatif, bütçe, anomali, fırsat, teşhis kuralları (deterministik)
├── tools/    # @function_tool sarmalayıcıları — agent'ın gördüğü arayüz
├── run_agent.py / send_report.py / dashboard.py   # Giriş noktaları
```

Katman akışı: **tools → meta/rules → client**. Araçlar ince sarmalayıcıdır;
asıl mantık `meta/` ve `rules/` içinde, test edilebilir saf fonksiyonlardadır.

## Konvansiyonlar

- **Salt okunur varsayılan.** Yazma araçları (`app/tools/meta_write.py`) yalnızca
  `ENABLE_WRITE_ACTIONS=true` iken çalışır ve agent önce kullanıcıdan açık onay alır.
  Oluşturulan her şey DURAKLATILMIŞ gelir. Harcamayı/durumu değiştiren araçlar
  (bütçe/aktifleştir/durdur) `dry_run=True` ile gerçek veriden bir önizleme
  döndürür (yazma yapmaz); agent önce önizler, onay alır, sonra `dry_run=False`
  ile uygular.
- **İzleme sağlığı** (`app/meta/tracking_health.py` + `app/rules/tracking_rules.py`):
  pikselin olay hunisini/tazeliğini denetler. Veri `client.get_pixels()` ve
  `client.get_pixel_stats()` salt-okunur metotlarından gelir. Kurallar saf ve
  test edilebilir; eşik eklemek için `tracking_rules.py`'a kural ekle.
- **Metrik uydurma yok.** Veriye yalnızca araçlar/`client.py` üzerinden erişilir;
  bir araç hata dönerse açıkça aktarılır, sayı uydurulmaz.
- **Test deseni:** yazma mantığı saf `_impl` yardımcılarında durur; `@function_tool`
  sarmalayıcıları yalnızca şemayı agent'a açar. Yeni araç eklerken aynı deseni izle
  ve `tests/` altına birim test ekle.
- **Dil:** Kullanıcıya yönelik metinler ve agent yanıtları Türkçedir; ton ölçülü,
  kurumsal ve emojisizdir (bkz. `meta_ads_agent.py` içindeki instructions).
- Yeni bir araç eklediğinde `app/agent/meta_ads_agent.py` içindeki `tools=[...]`
  listesine ve "HANGİ ARAÇ NE ZAMAN" yönergesine de eklemeyi unutma.

## Kalıcı hafıza (`app/meta/history.py`)

Agent verdiği önerileri ve günlük metrik snapshot'larını yerel SQLite'a
(`data/history.db`, `.gitignore`'da; `HISTORY_DB_PATH` ile değiştirilebilir) yazar.
`history.py` fonksiyonları daima açık bir `conn` alır — testler `connect(":memory:")`
kullanır. Snapshot'lar `app/send_report.py` içindeki `save_daily_snapshots()` ile
günlük cron'da otomatik birikir. Yeni metrik izlemek için `TRACKED_METRICS`'e
sütun ekle.
