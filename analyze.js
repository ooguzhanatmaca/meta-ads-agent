require('dotenv').config();
const axios = require('axios');

async function run() {
  const res = await axios.get(
    `https://graph.facebook.com/v21.0/${process.env.META_AD_ACCOUNT_ID}/insights`,
    {
      params: {
        fields:
          'campaign_name,spend,ctr,cpm,clicks,purchase_roas',
        level: 'campaign',
        date_preset: 'last_7d',
        access_token: process.env.META_ACCESS_TOKEN,
      },
    }
  );

  const data = res.data.data;

  const analyzed = data.map(c => {
    const roas =
      c.purchase_roas?.[0]?.value
        ? Number(c.purchase_roas[0].value)
        : 0;

    return {
      campaign: c.campaign_name,
      spend: Number(c.spend || 0),
      ctr: Number(c.ctr || 0),
      cpm: Number(c.cpm || 0),
      roas,
      score:
        roas * 40 +
        Number(c.ctr || 0) * 20 -
        Number(c.cpm || 0) * 0.1
    };
  });

  analyzed.sort((a, b) => b.score - a.score);

  console.log('\nEN İYİ REKLAMLAR\n');
  console.table(analyzed.slice(0, 5));

  console.log('\nEN KÖTÜ REKLAMLAR\n');
  console.table(analyzed.slice(-5));
}

run().catch(err => {
  console.log(err.response?.data || err.message);
});