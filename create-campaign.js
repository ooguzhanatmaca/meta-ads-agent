require('dotenv').config();
const readline = require('readline');
const { createCampaign, VALID_OBJECTIVES } = require('./src/creator/campaign');
const { COUNTRY_PRESETS, PRESET_LABELS, getCountries, getPresetLabel } = require('./src/config/targeting');

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

function ask(question, defaultVal) {
  const hint = defaultVal !== undefined ? ` [${defaultVal}]` : '';
  return new Promise((resolve) =>
    rl.question(`${question}${hint}: `, (ans) => resolve(ans.trim() || defaultVal || ''))
  );
}

async function main() {
  const safeMode = process.env.SAFE_MODE !== 'false';

  console.log('\n╔══════════════════════════════╗');
  console.log('║     KAMPANYA OLUŞTURUCU      ║');
  console.log('╚══════════════════════════════╝');
  console.log(`Güvenli mod: ${safeMode ? 'AÇIK ✓' : 'KAPALI ⚠'}`);
  console.log('Tüm kampanyalar PAUSED oluşturulur.\n');

  const defaultAccountId =
    process.env.ESSENCE_AD_ACCOUNT_ID ||
    (process.env.META_AD_ACCOUNT_IDS || '').split(',')[0].trim();

  const accountId = await ask('Reklam Hesap ID', defaultAccountId);
  if (!accountId) throw new Error('Hesap ID gerekli');

  const name = await ask('Kampanya adı');
  if (!name) throw new Error('Kampanya adı gerekli');

  console.log('\nObjective seçenekleri:');
  VALID_OBJECTIVES.forEach((o, i) => console.log(`  ${i + 1}. ${o}`));
  const objInput = await ask('Objective (1-4)', '1');
  const objective = VALID_OBJECTIVES[Number(objInput) - 1] || VALID_OBJECTIVES[0];

  const countries = getCountries();
  const presetLabel = getPresetLabel();
  console.log(`\nHedeflenen ülkeler (${presetLabel}): ${countries.join(', ')}`);
  console.log('Değiştirmek için .env içinde TARGET_COUNTRIES veya DEFAULT_TARGETING_PRESET ayarlayın.\n');

  console.log('─────────────────────────────────');
  console.log(`Hesap       : ${accountId}`);
  console.log(`Kampanya    : ${name}`);
  console.log(`Objective   : ${objective}`);
  console.log(`Status      : PAUSED`);
  console.log(`Ülkeler     : ${countries.join(', ')}`);
  console.log('─────────────────────────────────\n');

  const confirm = await ask('Oluşturmak istiyor musun? (evet/hayır)', 'evet');
  rl.close();

  if (!['evet', 'e', 'yes', 'y'].includes(confirm.toLowerCase())) {
    console.log('İptal edildi.');
    return;
  }

  console.log('\nKampanya oluşturuluyor...');
  const result = await createCampaign({ accountId, name, objective });

  console.log('\n✓ Kampanya oluşturuldu!');
  console.log(`  ID     : ${result.id}`);
  console.log(`  Status : PAUSED`);
  console.log(`  Ülkeler: ${countries.join(', ')}`);
}

main().catch((err) => {
  rl.close();
  console.error('\nHata:', err.response?.data?.error?.message || err.message);
  process.exitCode = 1;
});
