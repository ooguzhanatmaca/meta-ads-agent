require('dotenv').config();
const XLSX = require('xlsx');
const { trackPerformance } = require('./src/tracker/performance');
const { recommend, saveRecommendations } = require('./src/recommender/budget');
const { parseAdAccountIds } = require('./src/metaAccounts');

async function main() {
  const allAccountIds = parseAdAccountIds();
  const essenceId = process.env.ESSENCE_AD_ACCOUNT_ID;
  const accountIds = essenceId ? [essenceId] : allAccountIds;

  if (accountIds.length === 0) {
    console.error('Hesap ID bulunamadı.');
    process.exitCode = 1;
    return;
  }

  const datePreset = process.env.META_DATE_PRESET || 'last_7d';

  console.log('\n╔══════════════════════════════╗');
  console.log('║      BÜTÇE ÖNERİLERİ         ║');
  console.log('╚══════════════════════════════╝');
  console.log('Performans verisi çekiliyor...\n');

  const results = await trackPerformance(accountIds, datePreset);

  const campaignRecs = recommend(results.campaigns, 'campaign');
  const adsetRecs = recommend(results.adsets, 'adset');
  const allRecs = [...campaignRecs, ...adsetRecs];

  const actionable = allRecs.filter(
    (r) => r.action !== 'WATCH' && r.action !== 'WAIT'
  );

  const byAction = {
    PAUSE: allRecs.filter((r) => r.action === 'PAUSE'),
    INCREASE: allRecs.filter((r) => r.action === 'INCREASE'),
    DECREASE: allRecs.filter((r) => r.action === 'DECREASE'),
    WAIT: allRecs.filter((r) => r.action === 'WAIT'),
    WATCH: allRecs.filter((r) => r.action === 'WATCH'),
  };

  if (byAction.PAUSE.length > 0) {
    console.log(`\n🔴 DURDURMA ÖNERİSİ (${byAction.PAUSE.length} adet):`);
    console.table(byAction.PAUSE.map(fmt));
  }

  if (byAction.DECREASE.length > 0) {
    console.log(`\n🟡 BÜTÇE AZALT ÖNERİSİ (${byAction.DECREASE.length} adet):`);
    console.table(byAction.DECREASE.map(fmt));
  }

  if (byAction.INCREASE.length > 0) {
    console.log(`\n🟢 BÜTÇE ARTIR ÖNERİSİ (${byAction.INCREASE.length} adet):`);
    console.table(byAction.INCREASE.map(fmt));
  }

  if (byAction.WAIT.length > 0) {
    console.log(`\n⏳ BEKLE - YETERSİZ VERİ (${byAction.WAIT.length} adet):`);
    console.table(byAction.WAIT.map(fmt));
  }

  if (actionable.length === 0) {
    console.log('\nAksiyon gerektiren öneri yok. Tüm reklamlar izleme modunda.');
  }

  console.log(`\n── Özet ──────────────────────────`);
  console.log(`Durdur     : ${byAction.PAUSE.length}`);
  console.log(`Bütçe azalt: ${byAction.DECREASE.length}`);
  console.log(`Bütçe artır: ${byAction.INCREASE.length}`);
  console.log(`Bekle      : ${byAction.WAIT.length}`);
  console.log(`İzle       : ${byAction.WATCH.length}`);
  console.log(`──────────────────────────────────`);

  saveRecommendations(allRecs);
  console.log('\nÖneriler recommendations.json dosyasına kaydedildi.');

  const wb = XLSX.utils.book_new();
  const toSheet = (rows) =>
    XLSX.utils.json_to_sheet(rows.length ? rows : [{ empty: 'Veri yok' }]);

  XLSX.utils.book_append_sheet(wb, toSheet(allRecs), 'Tüm Öneriler');
  XLSX.utils.book_append_sheet(wb, toSheet(actionable), 'Aksiyon Gerekli');
  XLSX.utils.book_append_sheet(wb, toSheet(byAction.PAUSE), 'Durdur');
  XLSX.utils.book_append_sheet(wb, toSheet(byAction.INCREASE), 'Bütçe Artır');
  XLSX.utils.book_append_sheet(wb, toSheet(byAction.DECREASE), 'Bütçe Azalt');
  XLSX.writeFile(wb, 'recommendations.xlsx');
  console.log('Öneriler recommendations.xlsx dosyasına kaydedildi.');

  if (actionable.length > 0) {
    console.log('\nBütçe değişikliği uygulamak için: npm run apply-budget');
    console.log('(Önce .env dosyasında SAFE_MODE=false yapmanız gerekir)');
  }
}

function fmt(r) {
  return {
    seviye  : r.level,
    adı     : r.entity_name.slice(0, 30),
    eylem   : r.action,
    değişim : r.change_percent ? `${r.change_percent > 0 ? '+' : ''}${r.change_percent}%` : '-',
    harcama : r.spend,
    roas    : r.roas,
    neden   : r.reason.slice(0, 55),
  };
}

main().catch((err) => {
  console.error('\nHata:', err.response?.data?.error?.message || err.message);
  process.exitCode = 1;
});
