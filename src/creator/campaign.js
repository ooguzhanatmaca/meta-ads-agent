const axios = require('axios');

const VALID_OBJECTIVES = [
  'OUTCOME_LEADS',
  'OUTCOME_TRAFFIC',
  'OUTCOME_SALES',
  'OUTCOME_ENGAGEMENT',
];

async function createCampaign({ accountId, name, objective, specialAdCategories = ['NONE'] }) {
  if (!accountId) throw new Error('accountId gerekli');
  if (!name) throw new Error('Kampanya adı gerekli');
  if (!VALID_OBJECTIVES.includes(objective)) {
    throw new Error(`Geçersiz objective. Seçenekler: ${VALID_OBJECTIVES.join(', ')}`);
  }

  const apiVersion = process.env.META_API_VERSION || 'v21.0';

  const params = new URLSearchParams({
    name,
    objective,
    status: 'PAUSED',
    special_ad_categories: JSON.stringify(specialAdCategories),
    access_token: process.env.META_ACCESS_TOKEN,
  });

  const response = await axios.post(
    `https://graph.facebook.com/${apiVersion}/${accountId}/campaigns`,
    params
  );

  return response.data;
}

module.exports = { createCampaign, VALID_OBJECTIVES };
