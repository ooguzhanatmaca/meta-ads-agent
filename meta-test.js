require('dotenv').config();
const axios = require('axios');
const { parseAdAccountIds } = require('./src/metaAccounts');

async function run() {
  const token = process.env.META_ACCESS_TOKEN;
  const accountIds = parseAdAccountIds();

  const responses = await Promise.all(
    accountIds.map((accountId) => axios.get(
      `https://graph.facebook.com/v22.0/${accountId}`,
      {
        params: {
          fields: 'id,name,account_status',
          access_token: token,
        },
      }
    ).then((response) => ({ ad_account_id: accountId, account_name: response.data.name || '', ...response.data })))
  );

  console.log('META BAGLANTI BASARILI');
  console.table(responses);
}

run().catch(err => {
  console.log('HATA');
  console.log(err.response?.data || err.message);
});
