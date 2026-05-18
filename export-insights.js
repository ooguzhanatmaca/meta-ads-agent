require('dotenv').config();
const axios = require('axios');
const XLSX = require('xlsx');

async function run() {
  const res = await axios.get(
    `https://graph.facebook.com/v21.0/${process.env.META_AD_ACCOUNT_ID}/insights`,
    {
      params: {
        fields:
          'campaign_name,spend,clicks,ctr,cpm',
        level: 'campaign',
        date_preset: 'last_7d',
        access_token: process.env.META_ACCESS_TOKEN,
      },
    }
  );

  const data = res.data.data;

  const worksheet = XLSX.utils.json_to_sheet(data);
  const workbook = XLSX.utils.book_new();

  XLSX.utils.book_append_sheet(
    workbook,
    worksheet,
    'Meta Insights'
  );

  XLSX.writeFile(workbook, 'meta-insights.xlsx');

  console.log('EXCEL OLUŞTU');
}

run().catch(err => {
  console.log(err.response?.data || err.message);
});