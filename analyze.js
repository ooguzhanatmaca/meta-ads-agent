require('dotenv').config();
const axios = require('axios');
const { parseAdAccountIds, fetchAccountNames } = require('./src/metaAccounts');

async function run() {
  const accountIds = parseAdAccountIds();
  const accountNameMap = await fetchAccountNames(accountIds, process.env.META_ACCESS_TOKEN);
  const responses = await Promise.all(
    accountIds.map((accountId) => axios.get(
      `https://graph.facebook.com/v21.0/${accountId}/insights`,
      {
        params: {
          fields:
            'campaign_name,spend,ctr,cpm,clicks,purchase_roas',
          level: 'campaign',
          date_preset: 'last_7d',
          access_token: process.env.META_ACCESS_TOKEN,
        },
      }
    ).then((res) => (res.data.data || []).map((row) => ({
      ad_account_id: accountId,
      account_name: accountNameMap.get(accountId) || accountId,
      ...row,
    }))))
  );

  const data = responses.flat();

  const analyzed = data.map(c => {
    const roas =
      c.purchase_roas?.[0]?.value
        ? Number(c.purchase_roas[0].value)
        : 0;

    return {
      ad_account_id: c.ad_account_id,
      account_name: c.account_name || '',
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
