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
            'campaign_name,spend,clicks,ctr,cpm,actions,purchase_roas',
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

  console.table(responses.flat());
}

run().catch(err => {
  console.log(err.response?.data || err.message);
});
