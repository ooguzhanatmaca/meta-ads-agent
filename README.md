# Meta Ads AI Analyzer (Node.js)

Bu proje, Meta Ads kampanya verilerini cekip analiz eder:
- Campaign, adset ve ad insights cekme
- ROAS hesaplama
- CTR analizi
- CPM analizi
- En iyi / en kotu kampanyalari listeleme
- Excel export olusturma

## Kurulum

```bash
npm install
cp .env.example .env
```

`.env` icine gercek degerleri girin:

```env
META_ACCESS_TOKEN=your_meta_access_token
META_AD_ACCOUNT_IDS=act_1234567890,act_0987654321
META_API_VERSION=v21.0
META_DATE_PRESET=last_7d
```

Tek hesapli eski kullanim da desteklenir:

```env
META_AD_ACCOUNT_ID=act_1234567890
```

`META_AD_ACCOUNT_IDS` doluysa once o kullanilir. Rapor satirlarinda verinin geldigi hesap `ad_account_id` kolonu ile gosterilir.

## Calistirma

```bash
npm run analyze
```

Ciktilar:
- Terminalde kampanya analiz tablosu
- `meta-insights.xlsx` dosyasi
  - All Campaigns
  - Best Campaigns
  - Worst Campaigns

## Moduler yapi

- `src/config.js`: dotenv yukleme ve konfigurasyon
- `src/metaAccounts.js`: coklu/tekli Meta ad account env okuma
- `src/metaApi.js`: Meta Graph API cagrilari (axios)
- `src/analyzer.js`: ROAS/CTR/CPM analiz + skor
- `src/exporter.js`: Excel export (xlsx)
- `src/index.js`: uygulama akisi

## Not

Meta API erisimi icin gecerli access token ve en az bir dogru ad account id zorunludur.
