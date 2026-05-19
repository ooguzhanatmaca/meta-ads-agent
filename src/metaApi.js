const axios = require('axios');
const config = require('./config');
const { fetchAccountNames } = require('./metaAccounts');

function getBaseUrl(adAccountId) {
  return `https://graph.facebook.com/${config.apiVersion}/${adAccountId}`;
}

function validateConfig() {
  if (!config.accessToken || config.adAccountIds.length === 0) {
    throw new Error('META_ACCESS_TOKEN ve META_AD_ACCOUNT_IDS veya META_AD_ACCOUNT_ID zorunludur. .env dosyasini kontrol edin.');
  }
}

async function fetchInsightsForAccount(adAccountId, level) {
  const entityFields = {
    campaign: 'campaign_id,campaign_name',
    adset: 'campaign_id,campaign_name,adset_id,adset_name',
    ad: 'campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name',
  };

  const response = await axios.get(`${getBaseUrl(adAccountId)}/insights`, {
    params: {
      fields: `${entityFields[level]},spend,clicks,impressions,ctr,cpm,purchase_roas`,
      level,
      date_preset: config.datePreset,
      access_token: config.accessToken,
    },
  });

  return (response.data.data || []).map((row) => ({ ad_account_id: adAccountId, account_name: '', ...row }));
}

async function fetchCampaignInsights() {
  validateConfig();

  const accountNameMap = await fetchAccountNames(config.adAccountIds, config.accessToken);
  const results = await Promise.all(
    config.adAccountIds.map((adAccountId) =>
      fetchInsightsForAccount(adAccountId, 'campaign').then((rows) =>
        rows.map((row) => ({ ...row, account_name: accountNameMap.get(adAccountId) || adAccountId }))
      )
    )
  );

  return results.flat();
}

async function fetchAllInsights() {
  validateConfig();

  const accountNameMap = await fetchAccountNames(config.adAccountIds, config.accessToken);
  const results = await Promise.all(
    config.adAccountIds.map(async (adAccountId) => {
      const accountName = accountNameMap.get(adAccountId) || adAccountId;
      const addName = (rows) => rows.map((row) => ({ ...row, account_name: accountName }));
      return {
        adAccountId,
        accountName,
        campaigns: addName(await fetchInsightsForAccount(adAccountId, 'campaign')),
        adsets: addName(await fetchInsightsForAccount(adAccountId, 'adset')),
        ads: addName(await fetchInsightsForAccount(adAccountId, 'ad')),
      };
    })
  );

  return results;
}

module.exports = {
  fetchAllInsights,
  fetchCampaignInsights,
};
