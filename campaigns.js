require('dotenv').config();
const axios = require('axios');

async function run() {
  const res = await axios.get(
    `https://graph.facebook.com/v21.0/${process.env.META_AD_ACCOUNT_ID}/campaigns`,
    {
      params: {
        fields: 'id,name,status,effective_status,objective',
        access_token: process.env.META_ACCESS_TOKEN,
      },
    }
  );

  console.log('KAMPANYALAR');
  console.table(res.data.data);
}

run().catch(err => {
  console.log('HATA:', err.response?.data || err.message);
});