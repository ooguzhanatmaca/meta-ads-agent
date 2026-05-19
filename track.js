require('dotenv').config();
const { trackPerformance, exportToExcel } = require('./src/tracker/performance');
const { parseAdAccountIds } = require('./src/metaAccounts');

async function main() {
  const allAccountIds = parseAdAccountIds();
  const essenceId = process.env.ESSENCE_AD_ACCOUNT_ID;
  const accountIds = essenceId ? [essenceId] : allAccountIds;

  if (accountIds.length === 0) {
    console.error('Hesap ID bulunamadı. .env dosyasını kontrol edin.');
    process.exitCode = 1;
    return;
  }

  const datePreset = process.env.META_DATE_PRESET || 'last_7d';

  console.log('\n╔══════════════════════════════╗');
  console.log('║     PERFORMANS TAKİBİ        ║');
  console.log('╚══════════════════════════════╝');
  console.log(`Dönem   : ${datePreset}`);
  console.log(`Hesaplar: ${accountIds.join(', ')}\n`);

  const results = await trackPerformance(accountIds, datePreset);

  const totalSpend = results.adsets.reduce((s, r) => s + r.spend, 0);
  const warns = [...results.campaigns, ...results.adsets].filter((r) => r.status === 'WARN').length;
  const goods = [...results.campaigns, ...results.adsets].filter((r) => r.status === 'GOOD').length;

  console.log('\n══ KAMPANYA PERFORMANSI ══');
  if (results.campaigns.length === 0) {
    console.log('Kampanya verisi yok (bu dönemde harcama yapılmamış olabilir).');
  } else {
    console.table(
      results.campaigns.map((r) => ({
        'Kampanya'    : r.campaign_name.slice(0, 28),
        'Hesap'       : r.account_name,
        'Harcama'     : r.spend,
        'CTR%'        : r.ctr,
        'CPC'         : r.cpc,
        'Lead'        : r.leads,
        'Satın Alma'  : r.purchases,
        'ROAS'        : r.roas,
        'Durum'       : r.status,
        'Uyarı'       : r.flags || '-',
      }))
    );
  }

  console.log('\n══ ADSET PERFORMANSI ══');
  if (results.adsets.length === 0) {
    console.log('AdSet verisi yok.');
  } else {
    console.table(
      results.adsets.map((r) => ({
        'AdSet'        : r.adset_name.slice(0, 28),
        'Harcama'      : r.spend,
        'CTR%'         : r.ctr,
        'CPC'          : r.cpc,
        'CPM'          : r.cpm,
        'Lead'         : r.leads,
        'Satın Alma'   : r.purchases,
        'Cost/Lead'    : r.cost_per_lead,
        'Cost/Purchase': r.cost_per_purchase,
        'ROAS'         : r.roas,
        'Durum'        : r.status,
        'Uyarı'        : r.flags || '-',
      }))
    );
  }

  if (results.ads.length > 0) {
    console.log('\n══ REKLAM PERFORMANSI ══');
    console.table(
      results.ads.map((r) => ({
        'Reklam'    : r.ad_name.slice(0, 28),
        'Harcama'   : r.spend,
        'CTR%'      : r.ctr,
        'CPC'       : r.cpc,
        'Lead'      : r.leads,
        'Satın Alma': r.purchases,
        'ROAS'      : r.roas,
        'Durum'     : r.status,
        'Uyarı'     : r.flags || '-',
      }))
    );
  }

  console.log(`\n─────────────────────────────────`);
  console.log(`Toplam harcama  : ${Math.round(totalSpend * 100) / 100} TL`);
  console.log(`Uyarı sayısı    : ${warns}`);
  console.log(`İyi performans  : ${goods}`);

  const reportFile = 'performance-report.xlsx';
  exportToExcel(results, reportFile);
  console.log(`Rapor kaydedildi: ${reportFile}`);

  if (warns > 0) {
    console.log('\nBütçe önerileri için: npm run recommend');
  }
}

main().catch((err) => {
  console.error('\nHata:', err.response?.data?.error?.message || err.message);
  process.exitCode = 1;
});
