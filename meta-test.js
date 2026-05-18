require('dotenv').config();
const axios = require('axios');

async function run() {
  const token = process.env.META_ACCESS_TOKEN;
  const accountId = process.env.META_AD_ACCOUNT_ID;

  const response = await axios.get(
    `https://graph.facebook.com/v22.0/${accountId}`,
    {
      params: {
        fields: 'id,name,account_status',
        access_token: token,
      },
    }
  );

  console.log('META BAĞLANTI BAŞARILI');
  console.log(response.data);
}

run().catch(err => {
  console.log('HATA');
  console.log(err.response?.data || err.message);
});