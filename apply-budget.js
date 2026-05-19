require('dotenv').config();
const readline = require('readline');
const axios = require('axios');
const { loadRecommendations } = require('./src/recommender/budget');

const API_VERSION = process.env.META_API_VERSION || 'v21.0';
const ACCESS_TOKEN = process.env.META_ACCESS_TOKEN;
const SAFE_MODE = process.env.SAFE_MODE !== 'false';
const MAX_DAILY_BUDGET = Number(process.env.MAX_DAILY_BUDGET || 0);

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((resolve) => rl.question(`${q}: `, (a) => resolve(a.trim())));

async function getAdsetBudget(adsetId) {
  const response = await axios.get(
    `https://graph.facebook.com/${API_VERSION}/${adsetId}`,
    { params: { fields: 'id,name,daily_budget,status', access_token: ACCESS_TOKEN } }
  );
  return response.data;
}

async function updateAdsetBudget(adsetId, newBudget) {
  const params = new URLSearchParams({
    daily_budget: String(newBudget),
    access_token: ACCESS_TOKEN,
  });
  const response = await axios.post(
    `https://graph.facebook.com/${API_VERSION}/${adsetId}`,
    params
  );
  return response.data;
}

async function main() {
  console.log('\n╔══════════════════════════════╗');
  console.log('║      BÜTÇE UYGULAMA          ║');
  console.log('╚══════════════════════════════╝\n');

  // SAFE_MODE kontrolü — en kritik koruma
  if (SAFE_MODE) {
    console.error('SAFE_MODE aktif. Bütçe değişikliği yapılamaz.');
    console.error('');
    console.error('Bütçe değiştirmek için:');
    console.error('  1. .env dosyasını açın');
    console.error('  2. SAFE_MODE=false yapın');
    console.error('  3. npm run apply-budget çalıştırın');
    console.error('');
    console.error('İşlem sonrası SAFE_MODE=true yapmanızı öneririz.');
    rl.close();
    process.exitCode = 1;
    return;
  }

  console.log('⚠️  UYARI: SAFE_MODE KAPALI — gerçek bütçe değişiklikleri yapılacak!');
  if (MAX_DAILY_BUDGET > 0) {
    console.log(`Maksimum günlük bütçe limiti: ${MAX_DAILY_BUDGET / 100} TL`);
  }
  console.log('');

  const recommendations = loadRecommendations();
  if (recommendations.length === 0) {
    console.log('Öneri bulunamadı. Önce npm run recommend çalıştırın.');
    rl.close();
    return;
  }

  // Sadece adset seviyesinde INCREASE veya DECREASE olan öneriler
  const actionable = recommendations.filter(
    (r) =>
      r.level === 'adset' &&
      (r.action === 'INCREASE' || r.action === 'DECREASE') &&
      r.entity_id
  );

  if (actionable.length === 0) {
    console.log('Uygulanabilir adset bütçe değişikliği önerisi yok.');
    console.log('(PAUSE önerileri bu araçla değil, Ads Manager\'dan uygulanmalıdır)');
    rl.close();
    return;
  }

  // Mevcut bütçeleri çek ve değişimleri hesapla
  console.log('Mevcut bütçeler kontrol ediliyor...\n');
  const changes = [];

  for (const rec of actionable) {
    try {
      const adset = await getAdsetBudget(rec.entity_id);
      const currentBudget = Number(adset.daily_budget || 0);

      if (!currentBudget) {
        console.log(`  ⚠ ${rec.entity_name}: günlük bütçe alınamadı (lifetime budget?), atlanıyor.`);
        continue;
      }

      const newBudget = Math.round(currentBudget * (1 + rec.change_percent / 100));

      if (MAX_DAILY_BUDGET > 0 && newBudget > MAX_DAILY_BUDGET) {
        console.log(
          `  ⚠ ${rec.entity_name}: yeni bütçe ${newBudget / 100} TL, ` +
          `MAX_DAILY_BUDGET (${MAX_DAILY_BUDGET / 100} TL) aşıyor → atlanıyor.`
        );
        continue;
      }

      changes.push({
        id: rec.entity_id,
        name: rec.entity_name,
        action: rec.action,
        currentBudget,
        newBudget,
        reason: rec.reason,
      });
    } catch (err) {
      console.log(`  ⚠ ${rec.entity_name}: ${err.response?.data?.error?.message || err.message}`);
    }
  }

  if (changes.length === 0) {
    console.log('\nTüm değişiklikler atlandı. İşlem yapılmadı.');
    rl.close();
    return;
  }

  console.log('\nYapılacak değişiklikler:\n');
  console.table(
    changes.map((c) => ({
      'AdSet'       : c.name.slice(0, 30),
      'Eylem'       : c.action,
      'Mevcut'      : `${c.currentBudget / 100} TL`,
      'Yeni'        : `${c.newBudget / 100} TL`,
      'Fark'        : `${c.action === 'INCREASE' ? '+' : ''}${Math.round((c.newBudget - c.currentBudget) / 100 * 100) / 100} TL`,
      'Neden'       : c.reason.slice(0, 45),
    }))
  );

  console.log('\nBu değişiklikler gerçek reklam bütçelerini etkiler.');
  console.log('Onaylamak için "ONAYLA" yazın (tam büyük harf):');
  const confirm = await ask('');
  rl.close();

  if (confirm !== 'ONAYLA') {
    console.log('\nİptal edildi. Hiçbir değişiklik yapılmadı.');
    return;
  }

  console.log('\nBütçeler güncelleniyor...\n');
  let successCount = 0;
  let errorCount = 0;

  for (const change of changes) {
    try {
      await updateAdsetBudget(change.id, change.newBudget);
      console.log(
        `  ✓ ${change.name}: ${change.currentBudget / 100} TL → ${change.newBudget / 100} TL`
      );
      successCount++;
    } catch (err) {
      console.error(
        `  ✗ ${change.name}: ${err.response?.data?.error?.message || err.message}`
      );
      errorCount++;
    }
  }

  console.log(`\n── Tamamlandı ──────────────────────`);
  console.log(`Başarılı: ${successCount}`);
  console.log(`Hata    : ${errorCount}`);
  console.log(`────────────────────────────────────`);

  if (successCount > 0) {
    console.log('\nDeğişiklikler uygulandı. SAFE_MODE=true yapmayı unutmayın.');
  }
}

main().catch((err) => {
  rl.close();
  console.error('\nHata:', err.response?.data?.error?.message || err.message);
  process.exitCode = 1;
});
