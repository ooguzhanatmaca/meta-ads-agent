require('dotenv').config();

const axios = require('axios');
const XLSX = require('xlsx');
const { parseAdAccountIds, fetchAccountNames } = require('./src/metaAccounts');

const API_VERSION = process.env.META_API_VERSION || 'v21.0';
const ACCESS_TOKEN = process.env.META_ACCESS_TOKEN;
const AD_ACCOUNT_IDS = parseAdAccountIds();
const OUTPUT_FILE = 'meta-ai-report.xlsx';

const PERIODS = [
  { label: 'Last 7 Days', datePreset: 'last_7d', days: 7 },
  { label: 'Last 30 Days', datePreset: 'last_30d', days: 30 },
];

const THRESHOLDS = {
  highRoas: Number(process.env.HIGH_ROAS || 3),
  lowCpa: Number(process.env.LOW_CPA || 150),
  highCtr: Number(process.env.HIGH_CTR || 2),
  lowSpend: Number(process.env.LOW_SPEND || 1000),
  highSpend: Number(process.env.HIGH_SPEND_NO_PURCHASE || 1000),
  fatigueFrequency: Number(process.env.FATIGUE_FREQUENCY || 4),
  minPurchases: Number(process.env.MIN_PURCHASES || 3),
};

const METRIC_FIELDS = [
  'campaign_id',
  'campaign_name',
  'adset_id',
  'adset_name',
  'ad_id',
  'ad_name',
  'spend',
  'impressions',
  'clicks',
  'ctr',
  'cpm',
  'frequency',
  'actions',
  'action_values',
  'purchase_roas',
].join(',');

const BREAKDOWN_FIELDS = [
  'spend',
  'impressions',
  'clicks',
  'ctr',
  'cpm',
  'frequency',
  'actions',
  'action_values',
  'purchase_roas',
].join(',');

const ACTION_ALIASES = {
  purchase: ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase'],
  add_to_cart: ['add_to_cart', 'omni_add_to_cart', 'offsite_conversion.fb_pixel_add_to_cart'],
  initiate_checkout: ['initiate_checkout', 'omni_initiated_checkout', 'offsite_conversion.fb_pixel_initiate_checkout'],
};

const BREAKDOWNS = [
  { key: 'age', label: 'Age', breakdowns: ['age'] },
  { key: 'gender', label: 'Gender', breakdowns: ['gender'] },
  { key: 'age_gender', label: 'Age Gender', breakdowns: ['age', 'gender'] },
  { key: 'placement', label: 'Placement', breakdowns: ['publisher_platform', 'platform_position'] },
  { key: 'device', label: 'Device', breakdowns: ['device_platform'] },
  { key: 'country', label: 'Country', breakdowns: ['country'] },
];

const CREATIVE_FIELDS = [
  'id',
  'thumbnail_url',
  'image_url',
  'video_id',
  'body',
  'title',
  'call_to_action_type',
  'object_story_spec',
  'asset_feed_spec',
].join(',');

function validateConfig() {
  if (!ACCESS_TOKEN || AD_ACCOUNT_IDS.length === 0) {
    throw new Error('META_ACCESS_TOKEN ve META_AD_ACCOUNT_IDS veya META_AD_ACCOUNT_ID .env icinde zorunludur.');
  }
}

function baseUrl(pathName = '') {
  return `https://graph.facebook.com/${API_VERSION}/${pathName}`;
}

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function round(value, decimals = 2) {
  const factor = 10 ** decimals;
  return Math.round(toNumber(value) * factor) / factor;
}

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, value));
}

async function fetchPaginated(url, params) {
  const rows = [];
  let nextUrl = url;
  let nextParams = { ...params, access_token: ACCESS_TOKEN, limit: 500 };

  while (nextUrl) {
    const response = await axios.get(nextUrl, { params: nextParams });
    rows.push(...(response.data.data || []));
    nextUrl = response.data.paging?.next || null;
    nextParams = null;
  }

  return rows;
}

async function fetchInsights(adAccountId, level, period) {
  const rows = await fetchPaginated(baseUrl(`${adAccountId}/insights`), {
    fields: fieldsForLevel(level),
    level,
    date_preset: period.datePreset,
  });

  return rows.map((row) => ({ ad_account_id: adAccountId, account_name: '', ...row }));
}

function fieldsForLevel(level) {
  const fields = METRIC_FIELDS.split(',');
  if (level === 'campaign') return fields.filter((field) => !field.startsWith('adset_') && !field.startsWith('ad_')).join(',');
  if (level === 'adset') return fields.filter((field) => !field.startsWith('ad_')).join(',');
  return METRIC_FIELDS;
}

async function fetchCampaignBudgets(adAccountId) {
  const campaigns = await fetchPaginated(baseUrl(`${adAccountId}/campaigns`), {
    fields: 'id,name,status,daily_budget,lifetime_budget,budget_remaining',
  });

  return new Map(
    campaigns.map((campaign) => [
      `${adAccountId}:${campaign.id}`,
      {
        ad_account_id: adAccountId,
        status: campaign.status || '',
        daily_budget: centsToMoney(campaign.daily_budget),
        lifetime_budget: centsToMoney(campaign.lifetime_budget),
        budget_remaining: centsToMoney(campaign.budget_remaining),
      },
    ])
  );
}

function centsToMoney(value) {
  return value ? round(toNumber(value) / 100) : 0;
}

async function fetchBreakdown(adAccountId, config, period) {
  const rows = await fetchPaginated(baseUrl(`${adAccountId}/insights`), {
    fields: BREAKDOWN_FIELDS,
    breakdowns: config.breakdowns.join(','),
    date_preset: period.datePreset,
  });

  return rows.map((row) => ({ ad_account_id: adAccountId, ...row }));
}

async function fetchCreativeForAd(adId) {
  const response = await axios.get(baseUrl(adId), {
    params: {
      fields: `id,name,creative{${CREATIVE_FIELDS}}`,
      access_token: ACCESS_TOKEN,
    },
  });

  return response.data;
}

async function fetchCreatives(adIds) {
  const uniqueAdIds = [...new Set(adIds.filter(Boolean))];
  const creativeMap = new Map();
  const batchSize = 10;

  for (let i = 0; i < uniqueAdIds.length; i += batchSize) {
    const batch = uniqueAdIds.slice(i, i + batchSize);
    const results = await Promise.allSettled(batch.map(fetchCreativeForAd));

    results.forEach((result, index) => {
      const adId = batch[index];
      if (result.status !== 'fulfilled') {
        creativeMap.set(adId, { creative_error: result.reason.response?.data?.error?.message || result.reason.message });
        return;
      }

      const ad = result.value;
      const creative = ad.creative || {};
      const story = creative.object_story_spec || {};
      const link = story.link_data || {};
      const video = story.video_data || {};
      const assetFeed = creative.asset_feed_spec || {};

      creativeMap.set(adId, {
        ad_name: ad.name || '',
        creative_id: creative.id || '',
        thumbnail_url: creative.thumbnail_url || '',
        image_url: creative.image_url || link.picture || '',
        video_id: creative.video_id || video.video_id || '',
        body: creative.body || link.message || video.message || firstAssetText(assetFeed.bodies),
        title: creative.title || link.name || video.title || firstAssetText(assetFeed.titles),
        call_to_action:
          creative.call_to_action_type ||
          link.call_to_action?.type ||
          video.call_to_action?.type ||
          firstAssetText(assetFeed.call_to_action_types),
      });
    });
  }

  return creativeMap;
}

function firstAssetText(items) {
  if (!Array.isArray(items) || items.length === 0) return '';
  const first = items[0];
  if (typeof first === 'string') return first;
  return first.text || first.type || '';
}

function actionValue(actions, actionType) {
  if (!Array.isArray(actions)) return 0;
  const aliases = ACTION_ALIASES[actionType] || [actionType];
  return actions.filter((action) => aliases.includes(action.action_type)).reduce((sum, action) => sum + toNumber(action.value), 0);
}

function purchaseRoas(raw) {
  const spend = toNumber(raw.spend);
  const purchaseValue = actionValue(raw.action_values, 'purchase');
  if (spend > 0 && purchaseValue > 0) return purchaseValue / spend;
  if (Array.isArray(raw.purchase_roas) && raw.purchase_roas[0]) return toNumber(raw.purchase_roas[0].value);
  return 0;
}

function normalizeInsight(raw, level, period, creativeMap = new Map()) {
  const spend = toNumber(raw.spend);
  const purchases = actionValue(raw.actions, 'purchase');
  const clicks = toNumber(raw.clicks);
  const creative = level === 'ad' ? creativeMap.get(raw.ad_id) || {} : {};

  return {
    ad_account_id: raw.ad_account_id || '',
    account_name: raw.account_name || '',
    period: period.label,
    days: period.days,
    level,
    campaign_id: raw.campaign_id || '',
    campaign_name: raw.campaign_name || '',
    adset_id: raw.adset_id || '',
    adset_name: raw.adset_name || '',
    ad_id: raw.ad_id || '',
    ad_name: raw.ad_name || '',
    spend: round(spend),
    impressions: toNumber(raw.impressions),
    clicks,
    ctr: round(raw.ctr),
    cpm: round(raw.cpm),
    frequency: round(raw.frequency),
    purchases,
    purchase_value: round(actionValue(raw.action_values, 'purchase')),
    roas: round(purchaseRoas(raw)),
    cpa: purchases > 0 ? round(spend / purchases) : 0,
    conversion_rate: clicks > 0 ? round((purchases / clicks) * 100) : 0,
    creative_id: creative.creative_id || '',
    thumbnail_url: creative.thumbnail_url || '',
    image_url: creative.image_url || '',
    video_id: creative.video_id || '',
    body: creative.body || '',
    title: creative.title || '',
    call_to_action: creative.call_to_action || '',
    creative_error: creative.creative_error || '',
  };
}

function normalizeBreakdown(raw, config, period) {
  const spend = toNumber(raw.spend);
  const purchases = actionValue(raw.actions, 'purchase');
  const clicks = toNumber(raw.clicks);
  const key = config.breakdowns.map((field) => raw[field] || 'unknown').join(' | ');

  return {
    ad_account_id: raw.ad_account_id || '',
    account_name: raw.account_name || '',
    period: period.label,
    days: period.days,
    audience_type: config.label,
    audience_key: `${config.key}:${key}`,
    audience_value: key,
    age: raw.age || '',
    gender: raw.gender || '',
    placement: raw.platform_position || '',
    publisher_platform: raw.publisher_platform || '',
    device_platform: raw.device_platform || '',
    country: raw.country || '',
    spend: round(spend),
    purchases,
    purchase_value: round(actionValue(raw.action_values, 'purchase')),
    roas: round(purchaseRoas(raw)),
    cpa: purchases > 0 ? round(spend / purchases) : 0,
    ctr: round(raw.ctr),
    cpm: round(raw.cpm),
    frequency: round(raw.frequency),
    impressions: toNumber(raw.impressions),
    clicks,
    conversion_rate: clicks > 0 ? round((purchases / clicks) * 100) : 0,
  };
}

function groupBy(rows, keyFn) {
  const map = new Map();
  rows.forEach((row) => {
    const key = keyFn(row);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(row);
  });
  return map;
}

function aggregateRows(rows, extra = {}) {
  const spend = rows.reduce((sum, row) => sum + row.spend, 0);
  const impressions = rows.reduce((sum, row) => sum + row.impressions, 0);
  const clicks = rows.reduce((sum, row) => sum + row.clicks, 0);
  const purchases = rows.reduce((sum, row) => sum + row.purchases, 0);
  const purchaseValue = rows.reduce((sum, row) => sum + row.purchase_value, 0);
  const frequencyWeighted = rows.reduce((sum, row) => sum + row.frequency * row.impressions, 0);

  return {
    ...extra,
    spend: round(spend),
    impressions,
    clicks,
    purchases,
    purchase_value: round(purchaseValue),
    roas: spend > 0 ? round(purchaseValue / spend) : 0,
    cpa: purchases > 0 ? round(spend / purchases) : 0,
    ctr: impressions > 0 ? round((clicks / impressions) * 100) : 0,
    cpm: impressions > 0 ? round((spend / impressions) * 1000) : 0,
    frequency: impressions > 0 ? round(frequencyWeighted / impressions) : 0,
    conversion_rate: clicks > 0 ? round((purchases / clicks) * 100) : 0,
  };
}

function buildCampaignPerformance(campaignRows, budgetMap) {
  const grouped = groupBy(campaignRows, (row) => `${row.ad_account_id}:${row.campaign_id}`);

  return [...grouped.entries()].map(([campaignKey, rows]) => {
    const campaignId = rows[0]?.campaign_id || campaignKey;
    const last7 = rows.filter((row) => row.days === 7);
    const last30 = rows.filter((row) => row.days === 30);
    const perf7 = aggregateRows(last7);
    const perf30 = aggregateRows(last30);
    const budget = budgetMap.get(campaignKey) || {};
    const roasDelta = perf7.roas - perf30.roas;
    const cpaDelta = perf7.cpa && perf30.cpa ? perf7.cpa - perf30.cpa : 0;
    const confidence = scaleConfidence(perf7, perf30);
    const increasePercent = budgetIncreasePercent(perf7, perf30, confidence);

    return {
      ad_account_id: rows[0]?.ad_account_id || '',
      campaign_id: campaignId,
      campaign_name: rows[0]?.campaign_name || '',
      status: budget.status || '',
      current_daily_budget: budget.daily_budget || 0,
      recommended_budget_increase_percent: increasePercent,
      recommended_daily_budget:
        budget.daily_budget && increasePercent > 0 ? round(budget.daily_budget * (1 + increasePercent / 100)) : 0,
      scale_confidence_score: confidence,
      budget_recommendation:
        increasePercent > 0
          ? `Budget +${increasePercent}% onerilir`
          : perf7.frequency > THRESHOLDS.fatigueFrequency
            ? 'Frequency yuksek, budget artirma'
            : 'Budget sabit kalsin',
      reason: budgetReason(perf7, perf30, confidence),
      spend_7d: perf7.spend,
      purchases_7d: perf7.purchases,
      roas_7d: perf7.roas,
      cpa_7d: perf7.cpa,
      ctr_7d: perf7.ctr,
      frequency_7d: perf7.frequency,
      spend_30d: perf30.spend,
      purchases_30d: perf30.purchases,
      roas_30d: perf30.roas,
      cpa_30d: perf30.cpa,
      ctr_30d: perf30.ctr,
      frequency_30d: perf30.frequency,
      roas_delta_7d_vs_30d: round(roasDelta),
      cpa_delta_7d_vs_30d: round(cpaDelta),
    };
  }).sort((a, b) => b.scale_confidence_score - a.scale_confidence_score);
}

function scaleConfidence(perf7, perf30) {
  let score = 0;
  score += clamp((perf7.roas / THRESHOLDS.highRoas) * 35, 0, 35);
  score += perf7.cpa > 0 ? clamp((THRESHOLDS.lowCpa / perf7.cpa) * 25, 0, 25) : 0;
  score += clamp((perf7.ctr / THRESHOLDS.highCtr) * 15, 0, 15);
  score += clamp((perf7.purchases / THRESHOLDS.minPurchases) * 15, 0, 15);
  score += perf7.roas >= perf30.roas ? 10 : -10;
  score -= perf7.frequency > THRESHOLDS.fatigueFrequency ? 25 : 0;
  return round(clamp(score));
}

function budgetIncreasePercent(perf7, perf30, confidence) {
  if (perf7.frequency > THRESHOLDS.fatigueFrequency) return 0;
  if (perf7.roas < THRESHOLDS.highRoas || perf7.cpa <= 0 || perf7.cpa > THRESHOLDS.lowCpa) return 0;
  if (confidence >= 85 && perf7.roas >= perf30.roas) return 30;
  if (confidence >= 70) return 20;
  if (confidence >= 55) return 10;
  return 0;
}

function budgetReason(perf7, perf30, confidence) {
  if (perf7.frequency > THRESHOLDS.fatigueFrequency) return 'Frequency yuksek oldugu icin scale bloklandi.';
  if (perf7.roas >= THRESHOLDS.highRoas && perf7.cpa > 0 && perf7.cpa <= THRESHOLDS.lowCpa) {
    return `ROAS ${perf7.roas}, CPA ${perf7.cpa}, confidence ${confidence}.`;
  }
  if (perf7.spend >= THRESHOLDS.highSpend && perf7.purchases < THRESHOLDS.minPurchases) {
    return 'Spend yuksek ama purchase dusuk.';
  }
  return 'Performans izlenmeli.';
}

function buildCreativeScores(adRows) {
  const grouped = groupBy(adRows.filter((row) => row.days === 7), (row) => `${row.ad_account_id}:${row.creative_id || row.ad_id}`);

  return [...grouped.entries()].map(([creativeKey, rows]) => {
    const perf = aggregateRows(rows);
    const sample = rows[0] || {};
    const hookScore = hookPerformance(sample, perf);
    const thumbScore = thumbPerformance(sample, perf);
    const creativeScore = round(clamp(
      clamp((perf.ctr / 5) * 20, 0, 20) +
        clamp((perf.roas / 6) * 25, 0, 25) +
        hookScore * 0.15 +
        clamp((perf.conversion_rate / 8) * 15, 0, 15) +
        (perf.cpa > 0 ? clamp((THRESHOLDS.lowCpa / perf.cpa) * 15, 0, 15) : 0) +
        thumbScore * 0.1 -
        (perf.frequency > THRESHOLDS.fatigueFrequency ? 15 : 0)
    ));

    return {
      ad_account_id: sample.ad_account_id || '',
      creative_key: creativeKey,
      creative_id: sample.creative_id || '',
      ad_ids: rows.map((row) => row.ad_id).filter(Boolean).join(', '),
      ad_names: rows.map((row) => row.ad_name).filter(Boolean).join(' | '),
      title: sample.title || '',
      body: sample.body || '',
      thumbnail_url: sample.thumbnail_url || '',
      video_id: sample.video_id || '',
      hook_performance: hookScore,
      thumb_performance: thumbScore,
      creative_score: creativeScore,
      score_label: creativeScore >= 75 ? 'WINNER' : creativeScore <= 35 ? 'LOSER' : 'WATCH',
      ...perf,
    };
  }).sort((a, b) => b.creative_score - a.creative_score);
}

function hookPerformance(row, perf) {
  let score = 45;
  const text = `${row.title || ''} ${row.body || ''}`.trim();
  if (text.length > 20) score += 15;
  if (/[?]/.test(text)) score += 10;
  if (/\b(now|today|free|new|limited|save|stop|why|how|indirim|yeni|hemen|son)\b/i.test(text)) score += 10;
  if (row.video_id) score += 5;
  score += clamp((perf.ctr / THRESHOLDS.highCtr) * 15, 0, 15);
  return round(clamp(score));
}

function thumbPerformance(row, perf) {
  let score = row.thumbnail_url || row.image_url ? 35 : 15;
  score += clamp((perf.ctr / THRESHOLDS.highCtr) * 35, 0, 35);
  score += clamp((perf.roas / THRESHOLDS.highRoas) * 20, 0, 20);
  score -= perf.frequency > THRESHOLDS.fatigueFrequency ? 15 : 0;
  return round(clamp(score));
}

function buildAudienceRows(breakdownRows) {
  const enriched = compareAudiencePeriods(breakdownRows);
  return enriched.map((row) => {
    const decision = audienceDecision(row);
    return {
      ...row,
      audience_decision: decision,
      audience_reason: audienceReason(decision),
    };
  });
}

function compareAudiencePeriods(rows) {
  const grouped = groupBy(rows, (row) => `${row.ad_account_id}:${row.audience_key}`);
  return rows.map((row) => {
    const all = grouped.get(`${row.ad_account_id}:${row.audience_key}`) || [];
    const perf7 = aggregateRows(all.filter((item) => item.days === 7));
    const perf30 = aggregateRows(all.filter((item) => item.days === 30));
    return {
      ...row,
      roas_7d: perf7.roas,
      cpa_7d: perf7.cpa,
      ctr_7d: perf7.ctr,
      frequency_7d: perf7.frequency,
      roas_30d: perf30.roas,
      cpa_30d: perf30.cpa,
      ctr_30d: perf30.ctr,
      frequency_30d: perf30.frequency,
      trend_7d_vs_30d: perf7.roas > perf30.roas ? 'IMPROVING' : perf7.roas < perf30.roas ? 'DECLINING' : 'STABLE',
    };
  });
}

function audienceDecision(row) {
  const decisions = [];
  if (row.roas >= THRESHOLDS.highRoas && row.cpa > 0 && row.cpa <= THRESHOLDS.lowCpa) decisions.push('WINNING_AUDIENCE');
  if (row.frequency > THRESHOLDS.fatigueFrequency) decisions.push('SATURATED_AUDIENCE');
  if (row.spend >= THRESHOLDS.highSpend && row.purchases < THRESHOLDS.minPurchases) decisions.push('BAD_AUDIENCE');
  return decisions.length ? decisions.join(', ') : 'WATCH_AUDIENCE';
}

function audienceReason(decision) {
  if (decision.includes('WINNING_AUDIENCE')) return 'ROAS yuksek ve CPA dusuk.';
  if (decision.includes('SATURATED_AUDIENCE')) return 'Frequency yuksek, audience yoruluyor.';
  if (decision.includes('BAD_AUDIENCE')) return 'Spend yuksek ama purchase dusuk.';
  return 'Net aksiyon icin izlenmeli.';
}

function buildAudienceIntelligence(audienceRows) {
  const last7 = audienceRows.filter((row) => row.days === 7);
  const types = ['Age', 'Gender', 'Placement', 'Device', 'Country'];
  const accountIds = [...new Set(last7.map((row) => row.ad_account_id).filter(Boolean))];

  return accountIds.flatMap((adAccountId) => types.map((type) => {
    const rows = last7.filter((row) => row.ad_account_id === adAccountId && row.audience_type === type);
    const best = [...rows].sort((a, b) => b.roas - a.roas || a.cpa - b.cpa)[0] || {};
    const worst = [...rows].sort((a, b) => b.spend - a.spend || a.roas - b.roas)[0] || {};

    return {
      ad_account_id: adAccountId,
      category: type,
      best_segment: best.audience_value || '',
      best_roas: best.roas || 0,
      best_cpa: best.cpa || 0,
      best_ctr: best.ctr || 0,
      worst_or_heaviest_segment: worst.audience_value || '',
      worst_spend: worst.spend || 0,
      worst_roas: worst.roas || 0,
      summary: best.audience_value
        ? `${type} icinde en guclu segment ${best.audience_value}; ROAS ${best.roas}, CPA ${best.cpa}.`
        : `${type} icin yeterli veri yok.`,
    };
  }));
}

function detectOpportunities(adRows, creativeScores, audienceRows) {
  const last7Ads = adRows.filter((row) => row.days === 7);
  const highCtrLowSpend = last7Ads
    .filter((row) => row.ctr >= THRESHOLDS.highCtr && row.spend <= THRESHOLDS.lowSpend)
    .map((row) => opportunityRow('HIGH_CTR_LOW_SPEND', row, `CTR ${row.ctr}, spend ${row.spend}`));
  const lowCpaHighRoas = last7Ads
    .filter((row) => row.cpa > 0 && row.cpa <= THRESHOLDS.lowCpa && row.roas >= THRESHOLDS.highRoas)
    .map((row) => opportunityRow('LOW_CPA_HIGH_ROAS', row, `CPA ${row.cpa}, ROAS ${row.roas}`));
  const underScaledCreatives = creativeScores
    .filter((row) => row.creative_score >= 70 && row.spend <= THRESHOLDS.lowSpend)
    .map((row) => ({ ad_account_id: row.ad_account_id, opportunity_type: 'UNDER_SCALED_CREATIVE', entity_name: row.ad_names, score: row.creative_score, reason: 'Creative score yuksek ama spend dusuk.' }));
  const winningAudiences = audienceRows
    .filter((row) => row.days === 7 && row.audience_decision.includes('WINNING_AUDIENCE'))
    .map((row) => ({ ad_account_id: row.ad_account_id, opportunity_type: 'WINNING_AUDIENCE', entity_name: row.audience_value, score: row.roas, reason: row.audience_reason }));
  const saturatedAudiences = audienceRows
    .filter((row) => row.days === 7 && row.audience_decision.includes('SATURATED_AUDIENCE'))
    .map((row) => ({ ad_account_id: row.ad_account_id, opportunity_type: 'SATURATED_AUDIENCE', entity_name: row.audience_value, score: row.frequency, reason: row.audience_reason }));

  return [...highCtrLowSpend, ...lowCpaHighRoas, ...underScaledCreatives, ...winningAudiences, ...saturatedAudiences]
    .sort((a, b) => b.score - a.score);
}

function opportunityRow(type, row, reason) {
  return {
    ad_account_id: row.ad_account_id,
    opportunity_type: type,
    entity_name: row.ad_name || row.campaign_name,
    campaign_name: row.campaign_name,
    adset_name: row.adset_name,
    ad_id: row.ad_id,
    spend: row.spend,
    ctr: row.ctr,
    roas: row.roas,
    cpa: row.cpa,
    score: row.roas || row.ctr,
    reason,
  };
}

function buildExecutiveSummary(campaignPerf, adRows, creativeScores, opportunities) {
  const last7Ads = adRows.filter((row) => row.days === 7);
  const winners = [...creativeScores].slice(0, 5);
  const worstSpenders = [...last7Ads].sort((a, b) => b.spend - a.spend).filter((row) => row.purchases === 0 || row.roas < 1).slice(0, 5);
  const fatigue = [...last7Ads].filter((row) => row.frequency > THRESHOLDS.fatigueFrequency).sort((a, b) => b.frequency - a.frequency).slice(0, 5);
  const waste = worstSpenders.reduce((sum, row) => sum + row.spend, 0);
  const scaleCampaigns = campaignPerf.filter((row) => row.recommended_budget_increase_percent > 0).slice(0, 5);

  return [
    summaryRow('Top winners', winners.map((row) => `${row.ad_names || row.creative_id} (score ${row.creative_score})`).join(' | ')),
    summaryRow('Worst spenders', worstSpenders.map((row) => `${row.ad_name} spend ${row.spend}, ROAS ${row.roas}`).join(' | ')),
    summaryRow('Scale opportunities', scaleCampaigns.map((row) => `${row.campaign_name} +${row.recommended_budget_increase_percent}%`).join(' | ')),
    summaryRow('Creative fatigue alerts', fatigue.map((row) => `${row.ad_name} frequency ${row.frequency}`).join(' | ')),
    summaryRow('Budget waste', round(waste), 'Son 7 gunde purchase/ROAS zayif spend toplami.'),
    summaryRow('Suggested actions', opportunities.slice(0, 8).map((row) => `${row.opportunity_type}: ${row.entity_name}`).join(' | ')),
  ];
}

function summaryRow(section, value, note = '') {
  return { section, value: value || 'No data', note };
}

function buildAiRecommendations(adRows, creativeScoreMap) {
  return adRows
    .filter((row) => row.days === 7)
    .map((row) => {
      const creative = creativeScoreMap.get(`${row.ad_account_id}:${row.creative_id || row.ad_id}`) || {};
      return {
        ad_account_id: row.ad_account_id,
        campaign_name: row.campaign_name,
        adset_name: row.adset_name,
        ad_id: row.ad_id,
        ad_name: row.ad_name,
        spend: row.spend,
        ctr: row.ctr,
        roas: row.roas,
        cpa: row.cpa,
        frequency: row.frequency,
        creative_score: creative.creative_score || 0,
        recommendation: recommendationText(row, creative),
      };
    })
    .sort((a, b) => b.spend - a.spend);
}

function recommendationText(row, creative) {
  if (row.frequency > THRESHOLDS.fatigueFrequency) return 'Bu kreatif yuksek frequency nedeniyle yorulmus olabilir. Yeni varyasyon test edilmeli.';
  if (row.cpa > 0 && row.cpa <= THRESHOLDS.lowCpa && row.ctr >= THRESHOLDS.highCtr) {
    return 'Bu reklam dusuk CPA ve yuksek CTR nedeniyle olceklenebilir gorunuyor.';
  }
  if (row.roas >= THRESHOLDS.highRoas && row.purchases >= THRESHOLDS.minPurchases) return 'Bu reklam ROAS gucu nedeniyle kontrollu budget artisi icin aday.';
  if (row.spend >= THRESHOLDS.highSpend && row.purchases === 0) return 'Bu reklam spend tuketiyor ama purchase uretmiyor; pause veya hedefleme revizyonu onerilir.';
  if ((creative.creative_score || 0) >= 75 && row.spend <= THRESHOLDS.lowSpend) return 'Creative score yuksek ama spend dusuk; daha fazla trafikle test edilebilir.';
  if (row.ctr < 1) return 'CTR dusuk; kreatif acisi, thumbnail veya teklif metni yenilenmeli.';
  return 'Performans karisik; 24-48 saat daha izlenip CPA ve ROAS yonu takip edilmeli.';
}

function writeSheet(workbook, name, rows) {
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(rows.length ? rows : [{ empty: 'No data' }]), name);
}

function exportWorkbook(data) {
  const workbook = XLSX.utils.book_new();
  const creativeScoreMap = new Map(data.creativeScores.map((row) => [row.creative_key, row]));

  writeSheet(workbook, 'Executive Summary', data.executiveSummary);
  writeSheet(workbook, 'Budget Recommendations', data.campaignPerformance);
  writeSheet(workbook, 'Creative Score AI', data.creativeScores);
  writeSheet(workbook, 'Audience Intelligence', data.audienceIntelligence);
  writeSheet(workbook, 'Opportunity Detection', data.opportunities);
  writeSheet(workbook, 'AI Recommendation', buildAiRecommendations(data.adRows, creativeScoreMap));
  writeSheet(workbook, 'Campaigns', data.campaignRows);
  writeSheet(workbook, 'AdSets', data.adSetRows || []);
  writeSheet(workbook, 'Ads', data.adRows);
  writeSheet(workbook, 'Audience Rows', data.audienceRows);
  writeSheet(workbook, 'Scaling Audiences', data.audienceRows.filter((row) => row.days === 7 && row.audience_decision.includes('WINNING_AUDIENCE')));
  writeSheet(workbook, 'Bad Audiences', data.audienceRows.filter((row) => row.days === 7 && row.audience_decision.includes('BAD_AUDIENCE')));
  writeSheet(workbook, 'Saturated Audiences', data.audienceRows.filter((row) => row.days === 7 && row.audience_decision.includes('SATURATED_AUDIENCE')));

  XLSX.writeFile(workbook, OUTPUT_FILE);
}

async function main() {
  validateConfig();

  console.log('Hesap adlari cekiliyor...');
  const accountNameMap = await fetchAccountNames(AD_ACCOUNT_IDS, ACCESS_TOKEN);

  const raw = { campaign: [], adset: [], ad: [], breakdown: [] };

  console.log('Campaign budget bilgileri cekiliyor...');
  const budgetMaps = await Promise.all(AD_ACCOUNT_IDS.map((adAccountId) => fetchCampaignBudgets(adAccountId)));
  const budgetMap = new Map(budgetMaps.flatMap((map) => [...map.entries()]));

  for (const adAccountId of AD_ACCOUNT_IDS) {
    for (const period of PERIODS) {
      console.log(`${adAccountId} - ${period.label} campaign/ad insights cekiliyor...`);
      const [campaigns, adsets, ads] = await Promise.all([
        fetchInsights(adAccountId, 'campaign', period),
        fetchInsights(adAccountId, 'adset', period),
        fetchInsights(adAccountId, 'ad', period),
      ]);
      const addName = (row) => ({ ...row, account_name: accountNameMap.get(row.ad_account_id) || row.ad_account_id || '' });
      raw.campaign.push(...campaigns.map((row) => ({ row: addName(row), period })));
      raw.adset.push(...adsets.map((row) => ({ row: addName(row), period })));
      raw.ad.push(...ads.map((row) => ({ row: addName(row), period })));
    }

    for (const period of PERIODS) {
      console.log(`${adAccountId} - ${period.label} audience intelligence breakdown cekiliyor...`);
      const results = await Promise.allSettled(
        BREAKDOWNS.map((config) => fetchBreakdown(adAccountId, config, period).then((rows) => ({ config, rows })))
      );

      results.forEach((result, index) => {
        const config = BREAKDOWNS[index];
        if (result.status !== 'fulfilled') {
          console.warn(`${adAccountId} - ${config.label} breakdown alinamadi: ${result.reason.response?.data?.error?.message || result.reason.message}`);
          return;
        }
        raw.breakdown.push(...result.value.rows.map((row) => ({ row, period, config: result.value.config })));
      });
    }
  }

  const adIds = raw.ad.map(({ row }) => row.ad_id);
  console.log(`${new Set(adIds.filter(Boolean)).size} reklam icin creative bilgileri cekiliyor...`);
  const creativeMap = await fetchCreatives(adIds);

  const campaignRows = raw.campaign.map(({ row, period }) => normalizeInsight(row, 'campaign', period));
  const adSetRows = raw.adset.map(({ row, period }) => normalizeInsight(row, 'adset', period));
  const adRows = raw.ad.map(({ row, period }) => normalizeInsight(row, 'ad', period, creativeMap));
  const audienceRows = buildAudienceRows(raw.breakdown.map(({ row, period, config }) => normalizeBreakdown(row, config, period)));
  const campaignPerformance = buildCampaignPerformance(campaignRows, budgetMap);
  const creativeScores = buildCreativeScores(adRows);
  const audienceIntelligence = buildAudienceIntelligence(audienceRows);
  const opportunities = detectOpportunities(adRows, creativeScores, audienceRows);
  const executiveSummary = buildExecutiveSummary(campaignPerformance, adRows, creativeScores, opportunities);

  exportWorkbook({
    campaignRows,
    adSetRows,
    adRows,
    audienceRows,
    campaignPerformance,
    creativeScores,
    audienceIntelligence,
    opportunities,
    executiveSummary,
  });

  console.log(`\nAuto Media Buyer raporu olusturuldu: ${OUTPUT_FILE}`);
  console.log(`Budget recommendation: ${campaignPerformance.filter((row) => row.recommended_budget_increase_percent > 0).length}`);
  console.log(`Creative winner: ${creativeScores.filter((row) => row.score_label === 'WINNER').length}`);
  console.log(`Opportunity: ${opportunities.length}`);
}

main().catch((error) => {
  console.error('Hata:', error.response?.data || error.message);
  process.exitCode = 1;
});
