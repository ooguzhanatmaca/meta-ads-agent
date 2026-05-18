require('dotenv').config();
const axios = require('axios');

async function run() {
  const res = await axios.get(
    `https://graph.facebook.com/v21.0/${process.env.META_AD_ACCOUNT_ID}/insights`,
    {
      params: {
        fields:
          'campaign_name,spend,clicks,ctr,cpm,actions,purchase_roas',
        level: 'campaign',
        date_preset: 'last_7d',
        access_token: process.env.META_ACCESS_TOKEN,
      },
    }
  );

  console.table(res.data.data);
}

run().catch(err => {
  console.log(err.response?.data || err.message);
});