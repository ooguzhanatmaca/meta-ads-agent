const axios = require('axios');
const config = require('./config');

function getBaseUrl() {
  return `https://graph.facebook.com/${config.apiVersion}/${config.adAccountId}`;
}

function validateConfig() {
  if (!config.accessToken || !config.adAccountId) {
    throw new Error('META_ACCESS_TOKEN ve META_AD_ACCOUNT_ID zorunludur. .env dosyasını kontrol edin.');
  }
}

async function fetchCampaignInsights() {
  validateConfig();

  const response = await axios.get(`${getBaseUrl()}/insights`, {
    params: {
      fields: 'campaign_id,campaign_name,spend,clicks,impressions,ctr,cpm,purchase_roas',
      level: 'campaign',
      date_preset: config.datePreset,
      access_token: config.accessToken,
    },
  });

  return response.data.data || [];
}

module.exports = {
  fetchCampaignInsights,
};
