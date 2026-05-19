require('dotenv').config();
const readline = require('readline');
const axios = require('axios');
const { createCreative, createAd, CTA_OPTIONS } = require('./src/creator/ad');

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

function ask(question, defaultVal) {
  const hint = defaultVal !== undefined ? ` [${defaultVal}]` : '';
  return new Promise((resolve) =>
    rl.question(`${question}${hint}: `, (ans) => resolve(ans.trim() || defaultVal || ''))
  );
}

async function fetchAdsets(accountId) {
  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const response = await axios.get(
    `https://graph.facebook.com/${apiVersion}/${accountId}/adsets`,
    {
      params: {
        fields: 'id,name,status,campaign_id,daily_budget',
        limit: 50,
        access_token: process.env.META_ACCESS_TOKEN,
      },
    }
  );
  return response.data.data || [];
}

async function main() {
  console.log('\n╔══════════════════════════════╗');
  console.log('║      REKLAM OLUŞTURUCU       ║');
  console.log('╚══════════════════════════════╝');
  console.log('Tüm reklamlar PAUSED oluşturulur.\n');

  const defaultAccountId =
    process.env.ESSENCE_AD_ACCOUNT_ID ||
    (process.env.META_AD_ACCOUNT_IDS || '').split(',')[0].trim();

  const accountId = await ask('Reklam Hesap ID', defaultAccountId);
  if (!accountId) throw new Error('Hesap ID gerekli');

  const pageId = await ask('Facebook Page ID', process.env.ESSENCE_PAGE_ID || '');
  if (!pageId) throw new Error('Page ID gerekli (.env ESSENCE_PAGE_ID)');

  // AdSet seçimi
  console.log('\nAdSet\'ler yükleniyor...');
  const adsets = await fetchAdsets(accountId);

  if (adsets.length === 0) {
    console.log('Hesapta adset bulunamadı. Önce npm run create:adset çalıştırın.');
    rl.close();
    return;
  }

  console.log('\nMevcut AdSet\'ler:');
  adsets.forEach((a, i) => {
    const budget = a.daily_budget ? ` | ${Number(a.daily_budget) / 100} TL/gün` : '';
    console.log(`  ${i + 1}. [${a.status.padEnd(6)}] ${a.name.slice(0, 45)}${budget}`);
  });

  const adsetInput = await ask('\nAdSet seç (numara veya tam ID)');
  const adsetNum = Number(adsetInput);
  const adset =
    adsetNum > 0 && adsetNum <= adsets.length
      ? adsets[adsetNum - 1]
      : adsets.find((a) => a.id === adsetInput);

  if (!adset) throw new Error('Geçerli bir AdSet seçilmedi');
  console.log(`→ Seçilen: ${adset.name}`);

  const adName = await ask('\nReklam adı');
  if (!adName) throw new Error('Reklam adı gerekli');

  const creativeName = await ask('Creative adı', `${adName} - Creative`);

  // Reklam içeriği
  console.log('\n--- Reklam içeriği ---');
  const message = await ask('Ana metin (gönderi metni)');
  const linkTitle = await ask('Başlık');
  const description = await ask('Açıklama (opsiyonel)', '');
  const link = await ask('Hedef URL (website linki)');
  const imageHash = await ask('Görsel hash (varsa, boş bırakabilirsin)', '');
  const videoId = await ask('Video ID (varsa, boş bırakabilirsin)', '');

  console.log('\nCall-to-Action seçenekleri:');
  CTA_OPTIONS.forEach((c, i) => console.log(`  ${i + 1}. ${c}`));
  const ctaInput = await ask('CTA seç', '1');
  const callToAction = CTA_OPTIONS[Number(ctaInput) - 1] || 'LEARN_MORE';

  console.log('\n─────────────────────────────────');
  console.log(`Hesap     : ${accountId}`);
  console.log(`AdSet     : ${adset.name}`);
  console.log(`Reklam    : ${adName}`);
  console.log(`Metin     : ${message.slice(0, 60)}${message.length > 60 ? '...' : ''}`);
  console.log(`Başlık    : ${linkTitle}`);
  console.log(`Link      : ${link}`);
  console.log(`CTA       : ${callToAction}`);
  console.log(`Medya     : ${videoId ? `Video (${videoId})` : imageHash ? `Görsel hash (${imageHash})` : 'Yok'}`);
  console.log(`Status    : PAUSED`);
  console.log('─────────────────────────────────\n');

  const confirm = await ask('Oluşturmak istiyor musun? (evet/hayır)', 'evet');

  if (!['evet', 'e', 'yes', 'y'].includes(confirm.toLowerCase())) {
    rl.close();
    console.log('İptal edildi.');
    return;
  }

  console.log('\nCreative oluşturuluyor...');
  const creative = await createCreative({
    accountId,
    name: creativeName,
    pageId,
    message,
    link,
    linkTitle,
    description,
    imageHash: imageHash || undefined,
    videoId: videoId || undefined,
    callToAction,
  });
  console.log(`  Creative ID: ${creative.id}`);

  console.log('Reklam oluşturuluyor...');
  const ad = await createAd({
    accountId,
    adsetId: adset.id,
    name: adName,
    creativeId: creative.id,
  });

  rl.close();
  console.log('\n✓ Reklam oluşturuldu!');
  console.log(`  Ad ID       : ${ad.id}`);
  console.log(`  Creative ID : ${creative.id}`);
  console.log(`  Status      : PAUSED`);
}

main().catch((err) => {
  rl.close();
  console.error('\nHata:', err.response?.data?.error?.message || err.message);
  process.exitCode = 1;
});
