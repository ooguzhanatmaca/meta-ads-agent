const axios = require('axios');
const { buildTargeting } = require('../config/targeting');

// Objective'e göre optimizasyon ve ödeme ayarları
const OBJECTIVE_DEFAULTS = {
  OUTCOME_LEADS:      { optimizationGoal: 'LEAD_GENERATION',     billingEvent: 'IMPRESSIONS' },
  OUTCOME_TRAFFIC:    { optimizationGoal: 'LINK_CLICKS',         billingEvent: 'LINK_CLICKS' },
  OUTCOME_SALES:      { optimizationGoal: 'OFFSITE_CONVERSIONS', billingEvent: 'IMPRESSIONS' },
  OUTCOME_ENGAGEMENT: { optimizationGoal: 'POST_ENGAGEMENT',     billingEvent: 'IMPRESSIONS' },
};

async function createAdset({
  accountId,
  campaignId,
  name,
  dailyBudget,
  objective = 'OUTCOME_SALES',
  targeting = {},
  pixelId,
  pageId,
}) {
  if (!accountId) throw new Error('accountId gerekli');
  if (!campaignId) throw new Error('campaignId gerekli');
  if (!name) throw new Error('AdSet adı gerekli');
  if (!dailyBudget || Number(dailyBudget) < 100) {
    throw new Error('dailyBudget en az 100 (1 TL) olmalı');
  }

  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const accessToken = process.env.META_ACCESS_TOKEN;
  const targetingSpec = buildTargeting(targeting);
  const defaults = OBJECTIVE_DEFAULTS[objective] || OBJECTIVE_DEFAULTS.OUTCOME_SALES;

  const body = {
    name,
    campaign_id: campaignId,
    daily_budget: String(dailyBudget),
    billing_event: defaults.billingEvent,
    optimization_goal: defaults.optimizationGoal,
    targeting: JSON.stringify(targetingSpec),
    status: 'PAUSED',
    access_token: accessToken,
  };

  // Satış kampanyası için pixel ekle
  if (objective === 'OUTCOME_SALES' && pixelId) {
    body.promoted_object = JSON.stringify({
      pixel_id: pixelId,
      custom_event_type: 'PURCHASE',
    });
  }

  // Lead kampanyası için page ekle
  if (objective === 'OUTCOME_LEADS' && pageId) {
    body.promoted_object = JSON.stringify({ page_id: pageId });
  }

  const params = new URLSearchParams(body);

  const response = await axios.post(
    `https://graph.facebook.com/${apiVersion}/${accountId}/adsets`,
    params
  );

  return response.data;
}

module.exports = { createAdset, OBJECTIVE_DEFAULTS };
