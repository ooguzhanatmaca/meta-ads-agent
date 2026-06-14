# Meta Ads Agent

Meta (Facebook/Instagram) reklam hesabını **doğal dilde sohbet ederek** analiz eden,
profesyonel bir yapay zekâ reklam danışmanı. Performans analizi, kreatif değerlendirme,
bütçe önerileri, anomali tespiti, trend takibi ve raporlama yapar.

> **İki mod:**
> - **Analiz (varsayılan):** Agent yalnızca analiz eder ve önerir; Meta üzerinde
>   hiçbir değişiklik yapmaz.
> - **Operatör (opsiyonel):** `.env` içinde `ENABLE_WRITE_ACTIONS=true` yapılırsa
>   agent — açık onayınızla — kampanya/reklam seti/reklam oluşturabilir, durdurabilir,
>   aktifleştirebilir ve bütçe değiştirebilir. Varsayılan KAPALIDIR. Ayrıntı için
>   aşağıdaki [Operatör modu](#operatör-modu-yazma-işlemleri) bölümüne bakın.

---

## Özellikler

Agent sohbet içinde 28 araç kullanır (20 analiz + 8 operatör).

### Analiz araçları

| Konu | Ne yapar |
|------|----------|
| **Hesap özeti** | Son N günün performansı (harcama, ROAS, CPA, CTR, CPC, CPM...) |
| **Performans raporu** | Kampanya / reklam seti / reklam kırılımı |
| **Öneriler** | Kapatılmaya aday, bütçe artırılabilir reklamlar (gerekçeli) |
| **Fırsat bulucu** | Veri odaklı büyüme/strateji fikirleri ("ne deneyebilirim?") |
| **Kök neden analizi** | "Neden düştü/arttı?" — değişimin sebebini araştırır |
| **Kreatif sağlığı** | Kreatif yorgunluğu, sağlık skoru |
| **Görsel analizi** | Reklam görseline bakıp kreatif geri bildirim (Gemini vision) |
| **Reklam metni** | Yorulan kreatifler için yeni başlık/metin varyasyonları |
| **Bütçe önerileri** | Sayısal öneriler (önerilen günlük bütçe dahil) |
| **Demografik kırılım** | Yaş / cinsiyet / yerleşim / platform / ülke / cihaz |
| **Anomali uyarıları** | CPA artışı, ROAS düşüşü, satışsız harcama, kreatif yorgunluğu |
| **Trend** | Günlük trend + mini grafik (sparkline) ve yorum |
| **Senaryo (what-if)** | "Bütçeyi %X artırsam / kapatsam ne olur" tahmini |
| **Haftalık özet** | Bu hafta vs geçen hafta + en iyi/kötü reklamlar + uyarılar |
| **Dönem karşılaştırma** | Bugün/dün, son 7 gün/önceki 7 gün vb. |
| **Özel/benzer kitleler** | Hesaptaki özel (custom) kitleleri listeler |
| **Excel raporu** | Kapsamlı raporu `.xlsx` dosyası olarak kaydeder |
| **Yönetici özeti** | Tüm bulguları tek özette toplar |

### Operatör araçları (yazma — varsayılan KAPALI)

> Yalnızca `ENABLE_WRITE_ACTIONS=true` iken ve agent'ın açık onay istemesinden
> sonra çalışır. Oluşturulan her şey **DURAKLATILMIŞ** gelir (harcama başlamaz).

| Konu | Ne yapar |
|------|----------|
| **Kampanya oluştur** | Yeni kampanyayı duraklatılmış olarak açar |
| **Reklam seti oluştur** | Kampanya altında temel hedeflemeyle set kurar |
| **Kazanan seti klonla** | En iyi ROAS'lı setin gerçek ayarlarını kopyalayıp ölçekler |
| **Reklam oluştur** | Mevcut bir kreatifle reklam ekler |
| **Benzer (lookalike) kitle** | Kaynak kitleden lookalike kitle üretir |
| **Durdur / Aktifleştir** | Kampanya/set/reklamı duraklatır veya yayına alır |
| **Bütçe güncelle** | Günlük bütçeyi değiştirir (TL) |

Ek olarak:
- **Sohbet hafızası** — takip sorularını ("peki onu kapatsam?") hatırlar
- **Esnek tarih** — "son 30 gün", "bu ay", "dün" gibi dönemler
- **Çok modelli fallback** — bir model dolarsa otomatik sıradakini dener
- **Streamlit dashboard** — grafikli görsel panel (trend sekmesi dahil)
- **Günlük e-posta raporu** — uyarılı yönetici özetini Gmail ile gönderir

---

## Kurulum

Python 3.10+ gerekir.

```bash
# 1. Bağımlılıkları kur
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenleyip anahtarları gir (aşağıya bakın)
```

### `.env` ayarları

```bash
# Meta Marketing API (zorunlu)
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=act_...
META_GRAPH_API_VERSION=v21.0

# Yapay zekâ modeli (zorunlu) — Google Gemini ücretsiz başlar
GEMINI_API_KEY=...                       # aistudio.google.com
PRIMARY_MODEL=gemini/gemini-2.5-flash
FALLBACK_MODEL=gemini/gemini-flash-latest,gemini/gemini-2.5-pro,openai
VISION_MODEL=gemini/gemini-2.5-flash     # görsel analizi için

# OpenAI (opsiyonel — fallback zincirinde "openai")
OPENAI_API_KEY=...

# Günlük e-posta raporu (opsiyonel) — Gmail Uygulama Şifresi
SMTP_USER=...@gmail.com
SMTP_PASSWORD=...                        # Google "Uygulama Şifresi"
REPORT_TO=...@gmail.com

# Operatör modu (yazma işlemleri) — varsayılan KAPALI
ENABLE_WRITE_ACTIONS=false               # true yaparsanız agent hesabı değiştirebilir
```

> **Model notu:** Varsayılan Google Gemini'dir (ücretsiz katmanda günlük limit
> vardır). Yoğun kullanım için [aistudio.google.com](https://aistudio.google.com)
> üzerinden faturalandırmayı açmak limitleri kaldırır (Flash modelleri çok ucuzdur).
> `FALLBACK_MODEL` virgülle ayrılmış bir zincirdir; bir model kota/limit dolarsa
> otomatik sıradakine geçilir.

---

## Kullanım

```bash
# Agent ile sohbet (ana kullanım)
.venv/bin/python -m app.run_agent

# Günlük e-posta raporu (uyarılı yönetici özeti)
.venv/bin/python -m app.send_report

# Excel raporu (reports/ klasörüne .xlsx)
.venv/bin/python -m app.meta.export_excel

# Görsel panel (tarayıcıda açılır)
.venv/bin/python -m streamlit run app/dashboard.py
```

Sohbette örnek sorular:
- "Son 7 günde hesap nasıl gidiyor?"
- "En iyi kampanya hangisi?"
- "Hangi reklamları kapatmalıyım?"
- "Bu kampanyanın bütçesini %30 artırırsam ne olur?"
- "25-34 yaş grubu nasıl performans gösteriyor?"
- "Bu hafta nasıldı?" / "Excel raporu çıkar"
- "Yeni ne deneyebilirim?" / "Bu kampanya neden düştü?"
- (Operatör modu açıkken) "Kazanan reklam setini %50 bütçeyle klonla"

---

## Operatör modu (yazma işlemleri)

Varsayılan olarak agent **salt okunurdur**. Hesabı gerçekten değiştirmesini
isterseniz operatör modunu açın:

```bash
# .env
ENABLE_WRITE_ACTIONS=true
```

Güvenlik garantileri:

- **Varsayılan KAPALI:** `ENABLE_WRITE_ACTIONS` set edilmeden hiçbir yazma aracı
  çalışmaz; çağrılırsa "yazma işlemleri kapalı" yanıtı döner.
- **Açık onay:** Agent bir yazma aracını çağırmadan önce ne yapacağını özetler ve
  sizden onay ister. Onay vermeden işlem yapılmaz.
- **Hep duraklatılmış:** Oluşturulan kampanya/set/reklam DURAKLATILMIŞ gelir —
  siz Ads Manager'dan yayına almadıkça harcama başlamaz.
- **İzin:** Meta erişim token'ınız `ads_management` iznine sahip olmalıdır.

Harcamayı doğrudan etkileyen işlemler (`activate_entity`, `update_daily_budget`)
yalnızca çok net bir talepte çağrılır.

---

## Testler

```bash
.venv/bin/python -m pytest -q
```

---

## Proje yapısı

```
app/
├── agent/            # Agent tanımı + model fallback zinciri
├── meta/             # Meta API client, raporlar, trend, anomali, simülasyon, görsel
├── rules/            # Performans, kreatif, bütçe, anomali kuralları
├── tools/            # Agent araçları (@function_tool)
├── run_agent.py      # Sohbet arayüzü (terminal)
├── send_report.py    # E-posta raporu
└── dashboard.py      # Streamlit paneli
tests/                # Birim testler
```

---

## Güvenlik

- Agent **varsayılan olarak salt okunurdur**; yazma işlemleri ancak
  `ENABLE_WRITE_ACTIONS=true` iken ve açık onayınızla çalışır (bkz.
  [Operatör modu](#operatör-modu-yazma-işlemleri)).
- Oluşturulan her şey DURAKLATILMIŞ gelir; onayınız olmadan harcama başlamaz.
- `.env` dosyası (API anahtarları) `.gitignore`'dadır; sürüm kontrolüne girmez.
- Veri yalnızca araçlar üzerinden gelir; agent metrik uydurmaz.
