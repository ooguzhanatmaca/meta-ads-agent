require('dotenv').config();
const readline = require('readline');
const axios = require('axios');
const { createAdset } = require('./src/creator/adset');
const { COUNTRY_PRESETS, PRESET_LABELS } = require('./src/config/targeting');

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

function ask(question, defaultVal) {
  const hint = defaultVal !== undefined ? ` [${defaultVal}]` : '';
  return new Promise((resolve) =>
    rl.question(`${question}${hint}: `, (ans) => resolve(ans.trim() || defaultVal || ''))
  );
}

async function fetchCampaigns(accountId) {
  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const response = await axios.get(
    `https://graph.facebook.com/${apiVersion}/${accountId}/campaigns`,
    {
      params: {
        fields: 'id,name,objective,status',
        limit: 50,
        access_token: process.env.META_ACCESS_TOKEN,
      },
    }
  );
  return response.data.data || [];
}

async function main() {
  console.log('\n╔══════════════════════════════╗');
  console.log('║       ADSET OLUŞTURUCU       ║');
  console.log('╚══════════════════════════════╝');
  console.log('Tüm adsetler PAUSED oluşturulur.\n');

  const defaultAccountId =
    process.env.ESSENCE_AD_ACCOUNT_ID ||
    (process.env.META_AD_ACCOUNT_IDS || '').split(',')[0].trim();

  const accountId = await ask('Reklam Hesap ID', defaultAccountId);
  if (!accountId) throw new Error('Hesap ID gerekli');

  // Kampanya listesi
  console.log('\nKampanyalar yükleniyor...');
  const campaigns = await fetchCampaigns(accountId);

  if (campaigns.length === 0) {
    console.log('Hesapta kampanya bulunamadı. Önce npm run create:campaign çalıştırın.');
    rl.close();
    return;
  }

  console.log('\nMevcut kampanyalar:');
  campaigns.forEach((c, i) =>
    console.log(`  ${i + 1}. [${c.status.padEnd(6)}] ${c.name.slice(0, 45)} — ${c.objective}`)
  );

  const campInput = await ask('\nKampanya seç (numara veya tam ID)');
  const campNum = Number(campInput);
  const campaign =
    campNum > 0 && campNum <= campaigns.length
      ? campaigns[campNum - 1]
      : campaigns.find((c) => c.id === campInput);

  if (!campaign) throw new Error('Geçerli bir kampanya seçilmedi');
  console.log(`→ Seçilen: ${campaign.name} (${campaign.objective})`);

  const name = await ask('\nAdSet adı');
  if (!name) throw new Error('AdSet adı gerekli');

  const defaultBudget = process.env.DEFAULT_DAILY_BUDGET || '5000';
  const budgetInput = await ask('Günlük bütçe — kuruş cinsinden (5000 = 50 TL)', defaultBudget);
  const dailyBudget = Number(budgetInput);
  if (!dailyBudget || dailyBudget < 100) throw new Error('Minimum bütçe 100 (1 TL)');

  // Targeting preset
  const presetEntries = Object.entries(PRESET_LABELS);
  console.log('\nHedefleme presetleri:');
  presetEntries.forEach(([key, label], i) =>
    console.log(`  ${i + 1}. ${label}`)
  );
  console.log('  0. Özel (manuel ülke girişi)');

  const presetInput = await ask('Preset seç (0-5)', '1');
  let countries;
  const presetNum = Number(presetInput);

  if (presetNum === 0) {
    const custom = await ask('Ülke kodları (virgülle, örn: TR,DE,NL)');
    countries = custom.split(',').map((c) => c.trim()).filter(Boolean);
  } else {
    const [key] = presetEntries[presetNum - 1] || presetEntries[0];
    countries = COUNTRY_PRESETS[key];
  }

  if (!countries || countries.length === 0) throw new Error('En az bir ülke seçilmeli');

  const ageMin = Number(await ask('Minimum yaş', String(process.env.DEFAULT_AGE_MIN || '24')));
  const ageMax = Number(await ask('Maksimum yaş', String(process.env.DEFAULT_AGE_MAX || '50')));
  const genderInput = await ask('Cinsiyet (0=hepsi, 1=erkek, 2=kadın)', '0');
  const genders = genderInput === '0' ? undefined : [Number(genderInput)];
  const genderLabel = genderInput === '1' ? 'Erkek' : genderInput === '2' ? 'Kadın' : 'Hepsi';

  const pixelId = process.env.ESSENCE_PIXEL_ID;
  const pageId = process.env.ESSENCE_PAGE_ID;

  console.log('\n─────────────────────────────────');
  console.log(`Hesap       : ${accountId}`);
  console.log(`Kampanya    : ${campaign.name}`);
  console.log(`AdSet adı   : ${name}`);
  console.log(`Günlük bütçe: ${dailyBudget / 100} TL (${dailyBudget} kuruş)`);
  console.log(`Ülkeler     : ${countries.join(', ')}`);
  console.log(`Yaş         : ${ageMin} - ${ageMax}`);
  console.log(`Cinsiyet    : ${genderLabel}`);
  console.log(`Objective   : ${campaign.objective}`);
  if (pixelId) console.log(`Pixel ID    : ${pixelId}`);
  if (pageId)  console.log(`Page ID     : ${pageId}`);
  console.log(`Status      : PAUSED`);
  console.log('─────────────────────────────────\n');

  const confirm = await ask('Oluşturmak istiyor musun? (evet/hayır)', 'evet');
  rl.close();

  if (!['evet', 'e', 'yes', 'y'].includes(confirm.toLowerCase())) {
    console.log('İptal edildi.');
    return;
  }

  console.log('\nAdSet oluşturuluyor...');
  const result = await createAdset({
    accountId,
    campaignId: campaign.id,
    name,
    dailyBudget,
    objective: campaign.objective,
    targeting: { countries, age_min: ageMin, age_max: ageMax, genders },
    pixelId,
    pageId,
  });

  console.log('\n✓ AdSet oluşturuldu!');
  console.log(`  ID      : ${result.id}`);
  console.log(`  Status  : PAUSED`);
  console.log(`  Ülkeler : ${countries.join(', ')}`);
}

main().catch((err) => {
  rl.close();
  console.error('\nHata:', err.response?.data?.error?.message || err.message);
  process.exitCode = 1;
});
