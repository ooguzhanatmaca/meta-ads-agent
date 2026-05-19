require('dotenv').config();
const axios = require('axios');

async function main() {
  const keyword = process.argv[2];

  if (!keyword) {
    console.log('\nKullanım : node search-interests.js "<arama_terimi>"');
    console.log('Örnek    : node search-interests.js "kadın giyim"');
    console.log('           node search-interests.js "toptan"');
    console.log('           node search-interests.js "moda mağazası"');
    console.log('\nBulunan ID\'leri .env dosyasına ekleyin:');
    console.log('  ESSENCE_INTEREST_IDS=6003200501552,6003287410858,...\n');
    return;
  }

  const apiVersion = process.env.META_API_VERSION || 'v21.0';

  const response = await axios.get(`https://graph.facebook.com/${apiVersion}/search`, {
    params: {
      type: 'adinterest',
      q: keyword,
      limit: 20,
      locale: 'tr_TR',
      access_token: process.env.META_ACCESS_TOKEN,
    },
  });

  const interests = response.data.data || [];

  if (interests.length === 0) {
    console.log(`"${keyword}" için sonuç bulunamadı. Farklı bir terim deneyin.`);
    return;
  }

  console.log(`\n"${keyword}" için ilgi alanları:\n`);
  console.table(
    interests.map((i) => ({
      id: i.id,
      name: i.name,
      audience_size:
        i.audience_size_lower_bound
          ? `${(i.audience_size_lower_bound / 1e6).toFixed(1)}M - ${(i.audience_size_upper_bound / 1e6).toFixed(1)}M`
          : 'N/A',
      path: Array.isArray(i.path) ? i.path.join(' > ') : '',
    }))
  );

  const ids = interests.map((i) => i.id).join(',');
  console.log('\nBulduğun ID\'leri .env dosyasına ekle:');
  console.log(`  ESSENCE_INTEREST_IDS=${ids}\n`);
}

main().catch((err) => {
  console.error('Hata:', err.response?.data?.error?.message || err.message);
});
