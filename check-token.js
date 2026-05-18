require('dotenv').config();
const axios = require('axios');

async function run() {
  const token = process.env.META_ACCESS_TOKEN;

  const me = await axios.get('https://graph.facebook.com/v21.0/me', {
    params: { access_token: token }
  });

  console.log('TOKEN SAHİBİ:', me.data);

  const accounts = await axios.get('https://graph.facebook.com/v21.0/me/adaccounts', {
    params: {
      fields: 'id,name,account_status',
      access_token: token
    }
  });

  console.log('REKLAM HESAPLARI:', accounts.data);
}

run().catch(err => {
  console.log('HATA:', err.response?.data || err.message);
});