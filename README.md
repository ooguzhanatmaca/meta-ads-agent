# Meta Ads AI Analyzer (Node.js)

Bu proje, Meta Ads kampanya verilerini çekip analiz eder:
- Campaign insights çekme
- ROAS hesaplama
- CTR analizi
- CPM analizi
- En iyi / en kötü kampanyaları listeleme
- Excel export oluşturma

## Kurulum

```bash
npm install
cp .env.example .env
```

`.env` içine gerçek değerleri girin:

```env
META_ACCESS_TOKEN=your_meta_access_token
META_AD_ACCOUNT_ID=act_1234567890
META_API_VERSION=v21.0
META_DATE_PRESET=last_7d
```

## Çalıştırma

```bash
npm run analyze
```

Çıktılar:
- Terminalde kampanya analiz tablosu
- `meta-insights.xlsx` dosyası
  - All Campaigns
  - Best Campaigns
  - Worst Campaigns

## Modüler yapı

- `src/config.js`: dotenv yükleme ve konfigürasyon
- `src/metaApi.js`: Meta Graph API çağrıları (axios)
- `src/analyzer.js`: ROAS/CTR/CPM analiz + skor
- `src/exporter.js`: Excel export (xlsx)
- `src/index.js`: uygulama akışı

## Not

Meta API erişimi için geçerli access token ve doğru ad account id zorunludur.
