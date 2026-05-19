require('dotenv').config();

const axios = require('axios');
const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');
const { parseAdAccountIds, fetchAccountNames } = require('./src/metaAccounts');

const API_VERSION = process.env.META_API_VERSION || 'v21.0';
const ACCESS_TOKEN = process.env.META_ACCESS_TOKEN;
const AD_ACCOUNT_IDS = parseAdAccountIds();
const OUTPUT_FILE = 'meta-advanced-report.xlsx';
const PREVIEW_DIR = 'creative-previews';

const PERIODS = [
  { label: 'Last 7 Days', datePreset: 'last_7d', days: 7 },
  { label: 'Last 14 Days', datePreset: 'last_14d', days: 14 },
  { label: 'Last 30 Days', datePreset: 'last_30d', days: 30 },
];

const THRESHOLDS = {
  fatigueFrequency: Number(process.env.FATIGUE_FREQUENCY || 4),
  lowCtr: Number(process.env.LOW_CTR || 1),
  highRoas: Number(process.env.HIGH_ROAS || 3),
  highSpendNoPurchase: Number(process.env.HIGH_SPEND_NO_PURCHASE || 100),
  highCtr: Number(process.env.HIGH_CTR || 2),
  lowCpa: Number(process.env.LOW_CPA || 50),
  roasDropPercent: Number(process.env.ROAS_DROP_PERCENT || 20),
  lowAudiencePurchases: Number(process.env.LOW_AUDIENCE_PURCHASES || 1),
};

const METRIC_FIELDS = [
  'spend',
  'impressions',
  'clicks',
  'ctr',
  'cpc',
  'cpm',
  'frequency',
  'actions',
  'action_values',
  'purchase_roas',
];

const BREAKDOWN_PERIODS = PERIODS.filter((period) => period.days === 7 || period.days === 30);

const BREAKDOWN_CONFIGS = [
  {
    key: 'age_gender',
    analysisType: 'Age Gender',
    breakdowns: ['age', 'gender'],
    sheet: 'Age Gender Analysis',
  },
  {
    key: 'placement',
    analysisType: 'Placement',
    breakdowns: ['publisher_platform', 'platform_position'],
    sheet: 'Placement Analysis',
  },
  {
    key: 'device',
    analysisType: 'Device',
    breakdowns: ['device_platform'],
    sheet: 'Device Analysis',
  },
  {
    key: 'country',
    analysisType: 'Country',
    breakdowns: ['country'],
    sheet: 'Audience Analysis',
  },
];

const ACTION_ALIASES = {
  purchase: ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase'],
  add_to_cart: ['add_to_cart', 'omni_add_to_cart', 'offsite_conversion.fb_pixel_add_to_cart'],
  initiate_checkout: [
    'initiate_checkout',
    'omni_initiated_checkout',
    'offsite_conversion.fb_pixel_initiate_checkout',
  ],
};

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

function toNumber(value, defaultValue = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : defaultValue;
}

function round(value, decimals = 2) {
  const factor = 10 ** decimals;
  return Math.round(toNumber(value) * factor) / factor;
}

function sanitizeFileName(value) {
  return String(value || 'unknown')
    .replace(/[^a-z0-9-_]+/gi, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80);
}

function getBaseUrl(path = '') {
  return `https://graph.facebook.com/${API_VERSION}/${path}`;
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
  const rows = await fetchPaginated(getBaseUrl(`${adAccountId}/insights`), {
    fields: getInsightFields(level),
    level,
    date_preset: period.datePreset,
  });

  return rows.map((row) => ({ ad_account_id: adAccountId, ...row }));
}

async function fetchBreakdownInsights(adAccountId, config, period) {
  const rows = await fetchPaginated(getBaseUrl(`${adAccountId}/insights`), {
    fields: METRIC_FIELDS.join(','),
    breakdowns: config.breakdowns.join(','),
    date_preset: period.datePreset,
  });

  return rows.map((row) => ({ ad_account_id: adAccountId, ...row }));
}

function getInsightFields(level) {
  const entityFields = {
    campaign: ['campaign_id', 'campaign_name'],
    adset: ['campaign_id', 'campaign_name', 'adset_id', 'adset_name'],
    ad: ['campaign_id', 'campaign_name', 'adset_id', 'adset_name', 'ad_id', 'ad_name'],
  };

  return [...entityFields[level], ...METRIC_FIELDS].join(',');
}

async function fetchCreativeForAd(adId) {
  const response = await axios.get(getBaseUrl(adId), {
    params: {
      fields: `id,name,creative{${CREATIVE_FIELDS}}`,
      access_token: ACCESS_TOKEN,
    },
  });

  return response.data;
}

async function fetchCreativesForAds(adIds) {
  const uniqueAdIds = [...new Set(adIds.filter(Boolean))];
  const creativeMap = new Map();
  const batchSize = 10;

  for (let i = 0; i < uniqueAdIds.length; i += batchSize) {
    const batch = uniqueAdIds.slice(i, i + batchSize);
    const results = await Promise.allSettled(batch.map(fetchCreativeForAd));

    results.forEach((result, index) => {
      const adId = batch[index];

      if (result.status !== 'fulfilled') {
        creativeMap.set(adId, {
          ad_id: adId,
          creative_error: result.reason.response?.data?.error?.message || result.reason.message,
        });
        return;
      }

      const ad = result.value;
      const creative = ad.creative || {};
      const storySpec = creative.object_story_spec || {};
      const linkData = storySpec.link_data || {};
      const videoData = storySpec.video_data || {};
      const assetFeedSpec = creative.asset_feed_spec || {};

      creativeMap.set(adId, {
        ad_id: adId,
        ad_name: ad.name || '',
        creative_id: creative.id || '',
        thumbnail_url: creative.thumbnail_url || '',
        image_url: creative.image_url || linkData.picture || '',
        video_id: creative.video_id || videoData.video_id || '',
        body: creative.body || linkData.message || videoData.message || firstAssetText(assetFeedSpec.bodies),
        title: creative.title || linkData.name || videoData.title || firstAssetText(assetFeedSpec.titles),
        call_to_action:
          creative.call_to_action_type ||
          linkData.call_to_action?.type ||
          videoData.call_to_action?.type ||
          firstAssetText(assetFeedSpec.call_to_action_types),
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

function getActionValue(actions, actionType) {
  if (!Array.isArray(actions)) return 0;
  const aliases = ACTION_ALIASES[actionType] || [actionType];

  return actions
    .filter((item) => aliases.includes(item.action_type))
    .reduce((total, item) => total + toNumber(item.value), 0);
}

function getPurchaseRoas(purchaseRoas) {
  if (!Array.isArray(purchaseRoas) || purchaseRoas.length === 0) return 0;
  return toNumber(purchaseRoas[0].value);
}

function getPurchaseValue(actionValues) {
  return getActionValue(actionValues, 'purchase');
}

function getEntityId(raw, level) {
  if (level === 'campaign') return raw.campaign_id;
  if (level === 'adset') return raw.adset_id;
  return raw.ad_id;
}

function getEntityName(raw, level) {
  if (level === 'campaign') return raw.campaign_name;
  if (level === 'adset') return raw.adset_name;
  return raw.ad_name;
}

function normalizeInsight(raw, level, period, creativeMap = new Map(), accountNameMap = new Map()) {
  const spend = toNumber(raw.spend);
  const purchases = getActionValue(raw.actions, 'purchase');
  const roas = getPurchaseRoas(raw.purchase_roas);
  const frequency = toNumber(raw.frequency);
  const ctr = toNumber(raw.ctr);
  const cpc = toNumber(raw.cpc);
  const cpm = toNumber(raw.cpm);
  const creative = level === 'ad' ? creativeMap.get(raw.ad_id) || {} : {};

  return {
    ad_account_id: raw.ad_account_id || '',
    account_name: accountNameMap.get(raw.ad_account_id) || raw.ad_account_id || '',
    period: period.label,
    days: period.days,
    level,
    entity_id: getEntityId(raw, level) || '',
    entity_name: getEntityName(raw, level) || '',
    campaign_id: raw.campaign_id || '',
    campaign_name: raw.campaign_name || '',
    adset_id: raw.adset_id || '',
    adset_name: raw.adset_name || '',
    ad_id: raw.ad_id || '',
    ad_name: raw.ad_name || '',
    spend: round(spend),
    impressions: toNumber(raw.impressions),
    clicks: toNumber(raw.clicks),
    ctr: round(ctr),
    cpc: round(cpc),
    cpm: round(cpm),
    frequency: round(frequency),
    purchase: purchases,
    add_to_cart: getActionValue(raw.actions, 'add_to_cart'),
    initiate_checkout: getActionValue(raw.actions, 'initiate_checkout'),
    purchase_roas: round(roas),
    cost_per_purchase: purchases > 0 ? round(spend / purchases) : 0,
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

function normalizeBreakdownInsight(raw, config, period, accountNameMap = new Map()) {
  const spend = toNumber(raw.spend);
  const purchases = getActionValue(raw.actions, 'purchase');
  const purchaseValue = getPurchaseValue(raw.action_values);
  const roas = spend > 0 && purchaseValue > 0 ? purchaseValue / spend : getPurchaseRoas(raw.purchase_roas);
  const dimension = getBreakdownDimension(raw, config);

  return {
    ad_account_id: raw.ad_account_id || '',
    account_name: accountNameMap.get(raw.ad_account_id) || raw.ad_account_id || '',
    period: period.label,
    days: period.days,
    analysis_type: config.analysisType,
    breakdown_key: config.key,
    breakdowns: config.breakdowns.join(', '),
    audience_key: dimension.key,
    age: raw.age || '',
    gender: raw.gender || '',
    placement: raw.platform_position || raw.placement || '',
    publisher_platform: raw.publisher_platform || '',
    device_platform: raw.device_platform || '',
    country: raw.country || '',
    spend: round(spend),
    purchases,
    purchase_value: round(purchaseValue),
    roas: round(roas),
    cpa: purchases > 0 ? round(spend / purchases) : 0,
    ctr: round(raw.ctr),
    cpm: round(raw.cpm),
    frequency: round(raw.frequency),
    impressions: toNumber(raw.impressions),
    clicks: toNumber(raw.clicks),
  };
}

function getBreakdownDimension(raw, config) {
  const values = config.breakdowns.map((breakdown) => {
    if (breakdown === 'platform_position') return raw.platform_position || raw.placement || 'unknown';
    return raw[breakdown] || 'unknown';
  });

  return {
    key: `${config.key}:${values.join('|')}`,
  };
}

function addAudienceDecisions(rows) {
  return rows.map((row) => {
    const decisions = [];
    const reasons = [];

    if (row.roas >= THRESHOLDS.highRoas && row.cpa > 0 && row.cpa <= THRESHOLDS.lowCpa) {
      decisions.push('SCALING_AUDIENCE');
      reasons.push(`ROAS ${row.roas} >= ${THRESHOLDS.highRoas} ve CPA ${row.cpa} <= ${THRESHOLDS.lowCpa}`);
    }

    if (row.spend >= THRESHOLDS.highSpendNoPurchase && row.purchases <= THRESHOLDS.lowAudiencePurchases) {
      decisions.push('BAD_AUDIENCE');
      reasons.push(
        `Spend ${row.spend} >= ${THRESHOLDS.highSpendNoPurchase} ve purchase ${row.purchases} <= ${THRESHOLDS.lowAudiencePurchases}`
      );
    }

    if (row.frequency > THRESHOLDS.fatigueFrequency) {
      decisions.push('FATIGUE_AUDIENCE');
      reasons.push(`Frequency ${row.frequency} > ${THRESHOLDS.fatigueFrequency}`);
    }

    return {
      ...row,
      audience_decision: decisions.length ? decisions.join(', ') : 'WATCH_AUDIENCE',
      audience_reason: reasons.length ? reasons.join(' | ') : 'Audience performansi izleniyor',
    };
  });
}

function enrichAudienceComparison(rows) {
  const grouped = new Map();

  rows.forEach((row) => {
    const key = `${row.ad_account_id}|${row.breakdown_key}|${row.audience_key}`;
    const current = grouped.get(key) || {
      last7: emptyAudienceMetrics(),
      last30: emptyAudienceMetrics(),
    };

    if (row.days === 7) addAudienceMetrics(current.last7, row);
    if (row.days === 30) addAudienceMetrics(current.last30, row);

    grouped.set(key, current);
  });

  return rows.map((row) => {
    const comparison = grouped.get(`${row.ad_account_id}|${row.breakdown_key}|${row.audience_key}`) || {};
    const last7 = finalizeAudienceMetrics(comparison.last7 || emptyAudienceMetrics());
    const last30 = finalizeAudienceMetrics(comparison.last30 || emptyAudienceMetrics());
    const roasDelta = last7.roas - last30.roas;
    const cpaDelta = last7.cpa && last30.cpa ? last7.cpa - last30.cpa : 0;

    return {
      ...row,
      spend_7d: last7.spend,
      purchases_7d: last7.purchases,
      purchase_value_7d: last7.purchase_value,
      roas_7d: last7.roas,
      cpa_7d: last7.cpa,
      ctr_7d: last7.ctr,
      cpm_7d: last7.cpm,
      frequency_7d: last7.frequency,
      spend_30d: last30.spend,
      purchases_30d: last30.purchases,
      purchase_value_30d: last30.purchase_value,
      roas_30d: last30.roas,
      cpa_30d: last30.cpa,
      ctr_30d: last30.ctr,
      cpm_30d: last30.cpm,
      frequency_30d: last30.frequency,
      roas_delta_7d_vs_30d: round(roasDelta),
      cpa_delta_7d_vs_30d: round(cpaDelta),
      audience_trend:
        last30.roas > 0 && (last30.roas - last7.roas) / last30.roas >= THRESHOLDS.roasDropPercent / 100
          ? 'ROAS_DROP'
          : roasDelta > 0
            ? 'IMPROVING'
            : 'STABLE_OR_DOWN',
    };
  });
}

function emptyAudienceMetrics() {
  return {
    spend: 0,
    impressions: 0,
    clicks: 0,
    purchases: 0,
    purchase_value: 0,
    frequency_weighted: 0,
  };
}

function addAudienceMetrics(metrics, row) {
  metrics.spend += row.spend;
  metrics.impressions += row.impressions;
  metrics.clicks += row.clicks;
  metrics.purchases += row.purchases;
  metrics.purchase_value += row.purchase_value;
  metrics.frequency_weighted += row.frequency * row.impressions;
}

function finalizeAudienceMetrics(metrics) {
  return {
    spend: round(metrics.spend),
    purchases: metrics.purchases,
    purchase_value: round(metrics.purchase_value),
    roas: metrics.spend > 0 ? round(metrics.purchase_value / metrics.spend) : 0,
    cpa: metrics.purchases > 0 ? round(metrics.spend / metrics.purchases) : 0,
    ctr: metrics.impressions > 0 ? round((metrics.clicks / metrics.impressions) * 100) : 0,
    cpm: metrics.impressions > 0 ? round((metrics.spend / metrics.impressions) * 1000) : 0,
    frequency: metrics.impressions > 0 ? round(metrics.frequency_weighted / metrics.impressions) : 0,
  };
}

function getScalingAudiences(audienceRows) {
  return audienceRows
    .filter((row) => row.days === 7)
    .filter((row) => row.audience_decision.includes('SCALING_AUDIENCE'))
    .sort((a, b) => b.roas - a.roas || a.cpa - b.cpa);
}

function getBadAudiences(audienceRows) {
  return audienceRows
    .filter((row) => row.days === 7)
    .filter((row) => row.audience_decision.includes('BAD_AUDIENCE') || row.audience_decision.includes('FATIGUE_AUDIENCE'))
    .sort((a, b) => b.spend - a.spend || b.frequency - a.frequency);
}

function decide(row) {
  const reasons = [];

  if (row.frequency > THRESHOLDS.fatigueFrequency) {
    reasons.push(`Frequency ${row.frequency} > ${THRESHOLDS.fatigueFrequency}: kreatif yoruldu`);
  }

  if (row.spend >= THRESHOLDS.highSpendNoPurchase && row.purchase === 0) {
    return {
      decision: 'PAUSE',
      priority: 1,
      reason: [...reasons, `Harcama ${row.spend} ve satin alma yok`].join(' | '),
    };
  }

  if (row.ctr > 0 && row.ctr < THRESHOLDS.lowCtr) {
    return {
      decision: 'REFRESH_CREATIVE',
      priority: 2,
      reason: [...reasons, `CTR ${row.ctr} < ${THRESHOLDS.lowCtr}`].join(' | '),
    };
  }

  if (row.purchase_roas >= THRESHOLDS.highRoas && row.purchase > 0) {
    return {
      decision: 'SCALE',
      priority: 3,
      reason: [...reasons, `ROAS ${row.purchase_roas} >= ${THRESHOLDS.highRoas}`].join(' | '),
    };
  }

  if (reasons.length > 0) {
    return {
      decision: 'WATCH',
      priority: 4,
      reason: reasons.join(' | '),
    };
  }

  return {
    decision: 'WATCH',
    priority: 5,
    reason: 'Performansi izlemeye devam et',
  };
}

function addDecisions(rows) {
  return rows.map((row) => {
    const decision = decide(row);
    return { ...row, decision: decision.decision, decision_priority: decision.priority, reason: decision.reason };
  });
}

function summarizeRows(rows) {
  const grouped = new Map();

  rows.forEach((row) => {
    const key = `${row.ad_account_id}|${row.period}|${row.level}`;
    const current = grouped.get(key) || {
      ad_account_id: row.ad_account_id || '',
      period: row.period,
      level: row.level,
      spend: 0,
      impressions: 0,
      clicks: 0,
      purchase: 0,
      add_to_cart: 0,
      initiate_checkout: 0,
      revenue_proxy: 0,
      rows: 0,
      scale: 0,
      watch: 0,
      refresh_creative: 0,
      pause: 0,
    };

    current.spend += row.spend;
    current.impressions += row.impressions;
    current.clicks += row.clicks;
    current.purchase += row.purchase;
    current.add_to_cart += row.add_to_cart;
    current.initiate_checkout += row.initiate_checkout;
    current.revenue_proxy += row.spend * row.purchase_roas;
    current.rows += 1;
    current[row.decision.toLowerCase()] += 1;

    grouped.set(key, current);
  });

  return [...grouped.values()].map((row) => ({
    ad_account_id: row.ad_account_id,
    period: row.period,
    level: row.level,
    rows: row.rows,
    spend: round(row.spend),
    impressions: row.impressions,
    clicks: row.clicks,
    ctr: row.impressions > 0 ? round((row.clicks / row.impressions) * 100) : 0,
    cpc: row.clicks > 0 ? round(row.spend / row.clicks) : 0,
    cpm: row.impressions > 0 ? round((row.spend / row.impressions) * 1000) : 0,
    purchase: row.purchase,
    add_to_cart: row.add_to_cart,
    initiate_checkout: row.initiate_checkout,
    purchase_roas: row.spend > 0 ? round(row.revenue_proxy / row.spend) : 0,
    cost_per_purchase: row.purchase > 0 ? round(row.spend / row.purchase) : 0,
    SCALE: row.scale,
    WATCH: row.watch,
    REFRESH_CREATIVE: row.refresh_creative,
    PAUSE: row.pause,
  }));
}

function getCreativeRows(adRows) {
  const byCreative = new Map();

  adRows.forEach((row) => {
    const key = `${row.ad_account_id}:${row.creative_id || row.ad_id}`;
    const current = byCreative.get(key) || {
      ad_account_id: row.ad_account_id || '',
      creative_id: row.creative_id,
      creative_key: key,
      ad_ids: new Set(),
      ad_names: new Set(),
      campaign_names: new Set(),
      adset_names: new Set(),
      periods: new Set(),
      thumbnail_url: row.thumbnail_url,
      image_url: row.image_url,
      video_id: row.video_id,
      body: row.body,
      title: row.title,
      call_to_action: row.call_to_action,
      is_video: Boolean(row.video_id),
      spend: 0,
      impressions: 0,
      clicks: 0,
      purchase: 0,
      add_to_cart: 0,
      initiate_checkout: 0,
      revenue_proxy: 0,
      max_frequency: 0,
      decisions: new Set(),
    };

    current.ad_ids.add(row.ad_id);
    current.ad_names.add(row.ad_name);
    current.campaign_names.add(row.campaign_name);
    current.adset_names.add(row.adset_name);
    current.periods.add(row.period);
    current.spend += row.spend;
    current.impressions += row.impressions;
    current.clicks += row.clicks;
    current.purchase += row.purchase;
    current.add_to_cart += row.add_to_cart;
    current.initiate_checkout += row.initiate_checkout;
    current.revenue_proxy += row.spend * row.purchase_roas;
    current.max_frequency = Math.max(current.max_frequency, row.frequency);
    current.decisions.add(row.decision);

    byCreative.set(key, current);
  });

  return [...byCreative.values()].map((row) => ({
    ad_account_id: row.ad_account_id,
    creative_id: row.creative_id,
    creative_key: row.creative_key,
    reused: row.ad_ids.size > 1 ? 'YES' : 'NO',
    usage_count: row.ad_ids.size,
    ad_ids: [...row.ad_ids].filter(Boolean).join(', '),
    ad_names: [...row.ad_names].filter(Boolean).join(' | '),
    campaign_names: [...row.campaign_names].filter(Boolean).join(' | '),
    adset_names: [...row.adset_names].filter(Boolean).join(' | '),
    periods: [...row.periods].join(', '),
    thumbnail_url: row.thumbnail_url,
    image_url: row.image_url,
    video_id: row.video_id,
    is_video: row.is_video ? 'YES' : 'NO',
    body: row.body,
    title: row.title,
    call_to_action: row.call_to_action,
    spend: round(row.spend),
    impressions: row.impressions,
    clicks: row.clicks,
    ctr: row.impressions > 0 ? round((row.clicks / row.impressions) * 100) : 0,
    purchase: row.purchase,
    add_to_cart: row.add_to_cart,
    initiate_checkout: row.initiate_checkout,
    purchase_roas: row.spend > 0 ? round(row.revenue_proxy / row.spend) : 0,
    cost_per_purchase: row.purchase > 0 ? round(row.spend / row.purchase) : 0,
    max_frequency: round(row.max_frequency),
    hook_analysis: getHookAnalysis(row),
    decisions: [...row.decisions].join(', '),
  })).map(addCreativeScore);
}

function getHookAnalysis(row) {
  if (!row.is_video) return '';

  const hookText = [row.title, row.body].filter(Boolean).join(' ').slice(0, 160);
  if (!hookText) return 'VIDEO_HOOK_REVIEW_NEEDED';
  if (/[?]/.test(hookText)) return `QUESTION_HOOK: ${hookText}`;
  if (/\b(now|today|free|new|limited|save|stop|why|how)\b/i.test(hookText)) return `STRONG_HOOK_SIGNAL: ${hookText}`;
  return `MANUAL_HOOK_REVIEW: ${hookText}`;
}

function addCreativeScore(row) {
  const roasScore = Math.min(row.purchase_roas, 6) * 12;
  const ctrScore = Math.min(row.ctr, 8) * 8;
  const cpaPenalty = row.cost_per_purchase > 0 ? Math.min(row.cost_per_purchase / 5, 25) : 10;
  const fatiguePenalty = row.max_frequency > THRESHOLDS.fatigueFrequency ? (row.max_frequency - THRESHOLDS.fatigueFrequency) * 8 : 0;
  const purchaseScore = Math.min(row.purchase, 20) * 1.5;
  const reuseBonus = row.usage_count > 1 ? 5 : 0;
  const score = round(roasScore + ctrScore + purchaseScore + reuseBonus - cpaPenalty - fatiguePenalty);

  return {
    ...row,
    creative_winner_score: score,
    visual_performance_rank: '',
  };
}

function rankCreatives(creativeRows) {
  return [...creativeRows]
    .sort((a, b) => b.creative_winner_score - a.creative_winner_score || b.ctr - a.ctr)
    .map((row, index) => ({
      ...row,
      visual_performance_rank: index + 1,
    }));
}

function getCreativeKey(row) {
  return `${row.ad_account_id || ''}:${row.creative_id || row.ad_id || row.creative_key}`;
}

function buildCreativePeriodComparison(adRows) {
  const grouped = new Map();

  adRows.forEach((row) => {
    const key = getCreativeKey(row);
    const current = grouped.get(key) || {
      ad_account_id: row.ad_account_id || '',
      creative_key: key,
      creative_id: row.creative_id,
      ad_ids: new Set(),
      title: row.title,
      body: row.body,
      thumbnail_url: row.thumbnail_url,
      last7: emptyMetrics(),
      last30: emptyMetrics(),
    };

    current.ad_ids.add(row.ad_id);
    if (row.days === 7) addMetrics(current.last7, row);
    if (row.days === 30) addMetrics(current.last30, row);

    grouped.set(key, current);
  });

  return [...grouped.values()].map((row) => {
    const last7 = finalizeMetrics(row.last7);
    const last30 = finalizeMetrics(row.last30);
    const roasDrop = last30.purchase_roas > 0 ? ((last30.purchase_roas - last7.purchase_roas) / last30.purchase_roas) * 100 : 0;

    return {
      ad_account_id: row.ad_account_id,
      creative_id: row.creative_id,
      creative_key: row.creative_key,
      ad_ids: [...row.ad_ids].filter(Boolean).join(', '),
      title: row.title,
      thumbnail_url: row.thumbnail_url,
      spend_7d: last7.spend,
      ctr_7d: last7.ctr,
      cpa_7d: last7.cost_per_purchase,
      roas_7d: last7.purchase_roas,
      purchase_7d: last7.purchase,
      spend_30d: last30.spend,
      ctr_30d: last30.ctr,
      cpa_30d: last30.cost_per_purchase,
      roas_30d: last30.purchase_roas,
      purchase_30d: last30.purchase,
      roas_drop_percent: round(roasDrop),
      roas_trend:
        roasDrop >= THRESHOLDS.roasDropPercent
          ? 'ROAS_DROP'
          : last7.purchase_roas > last30.purchase_roas
            ? 'ROAS_UP'
            : 'STABLE',
    };
  });
}

function emptyMetrics() {
  return {
    spend: 0,
    impressions: 0,
    clicks: 0,
    purchase: 0,
    revenue_proxy: 0,
  };
}

function addMetrics(metrics, row) {
  metrics.spend += row.spend;
  metrics.impressions += row.impressions;
  metrics.clicks += row.clicks;
  metrics.purchase += row.purchase;
  metrics.revenue_proxy += row.spend * row.purchase_roas;
}

function finalizeMetrics(metrics) {
  return {
    spend: round(metrics.spend),
    ctr: metrics.impressions > 0 ? round((metrics.clicks / metrics.impressions) * 100) : 0,
    cost_per_purchase: metrics.purchase > 0 ? round(metrics.spend / metrics.purchase) : 0,
    purchase_roas: metrics.spend > 0 ? round(metrics.revenue_proxy / metrics.spend) : 0,
    purchase: metrics.purchase,
  };
}

function getScalingOpportunities(adRows) {
  return adRows
    .filter((row) => row.days === 7)
    .filter((row) => row.cost_per_purchase > 0 && row.cost_per_purchase <= THRESHOLDS.lowCpa && row.ctr >= THRESHOLDS.highCtr)
    .map((row) => ({
      ...row,
      opportunity_type: 'LOW_CPA_HIGH_CTR',
      opportunity_reason: `CPA ${row.cost_per_purchase} <= ${THRESHOLDS.lowCpa} ve CTR ${row.ctr} >= ${THRESHOLDS.highCtr}`,
    }))
    .sort((a, b) => b.purchase_roas - a.purchase_roas || a.cost_per_purchase - b.cost_per_purchase);
}

function getCreativeWinners(creativeRows) {
  return creativeRows
    .filter((row) => row.purchase > 0 || row.ctr >= THRESHOLDS.highCtr)
    .sort((a, b) => b.creative_winner_score - a.creative_winner_score)
    .slice(0, 50);
}

function getCreativeLosers(creativeRows, comparisonRows) {
  const roasDrops = new Set(
    comparisonRows.filter((row) => row.roas_trend === 'ROAS_DROP').map((row) => row.creative_key)
  );

  return creativeRows
    .filter((row) => row.max_frequency > THRESHOLDS.fatigueFrequency || row.purchase_roas === 0 || roasDrops.has(row.creative_key))
    .map((row) => ({
      ...row,
      loser_reason: [
        row.max_frequency > THRESHOLDS.fatigueFrequency ? 'HIGH_FREQUENCY' : '',
        row.purchase_roas === 0 ? 'NO_ROAS' : '',
        roasDrops.has(row.creative_key) ? 'ROAS_DROP' : '',
      ].filter(Boolean).join(', '),
    }))
    .sort((a, b) => a.creative_winner_score - b.creative_winner_score)
    .slice(0, 50);
}

function getFatigueAlerts(adRows, creativeRows) {
  const creativeByKey = new Map(creativeRows.map((row) => [row.creative_key, row]));

  return adRows
    .filter((row) => row.frequency > THRESHOLDS.fatigueFrequency)
    .map((row) => {
      const creative = creativeByKey.get(getCreativeKey(row)) || {};
      return {
        ...row,
        creative_winner_score: creative.creative_winner_score || 0,
        alert: `Frequency ${row.frequency} > ${THRESHOLDS.fatigueFrequency}`,
      };
    })
    .sort((a, b) => b.frequency - a.frequency || b.spend - a.spend);
}

async function enrichCreativePreviews(creativeRows) {
  fs.mkdirSync(PREVIEW_DIR, { recursive: true });

  const enriched = [];

  for (const row of creativeRows) {
    const baseName = sanitizeFileName(row.creative_id || row.creative_key);
    const thumbnailPath = row.thumbnail_url ? await downloadImage(row.thumbnail_url, baseName) : '';
    const previewPath = createPreviewHtml(row, thumbnailPath, baseName);

    enriched.push({
      ...row,
      local_thumbnail_path: thumbnailPath,
      local_preview_path: previewPath,
    });
  }

  return enriched;
}

async function downloadImage(url, baseName) {
  try {
    const response = await axios.get(url, {
      responseType: 'arraybuffer',
      timeout: 30000,
    });
    const extension = getImageExtension(response.headers['content-type'], url);
    const filePath = path.join(PREVIEW_DIR, `${baseName}${extension}`);

    fs.writeFileSync(filePath, response.data);
    return filePath;
  } catch (error) {
    return `DOWNLOAD_FAILED: ${error.response?.status || error.message}`;
  }
}

function getImageExtension(contentType, url) {
  if (contentType?.includes('png')) return '.png';
  if (contentType?.includes('webp')) return '.webp';
  if (contentType?.includes('gif')) return '.gif';

  const urlExtension = path.extname(new URL(url).pathname);
  return urlExtension || '.jpg';
}

function createPreviewHtml(row, thumbnailPath, baseName) {
  const filePath = path.join(PREVIEW_DIR, `${baseName}.html`);
  const imageSource = thumbnailPath && !thumbnailPath.startsWith('DOWNLOAD_FAILED') ? path.basename(thumbnailPath) : row.thumbnail_url;
  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(row.creative_id || row.creative_key)}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; color: #111827; background: #f8fafc; }
    main { max-width: 760px; margin: 0 auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }
    img { max-width: 100%; border-radius: 6px; border: 1px solid #e5e7eb; }
    dl { display: grid; grid-template-columns: 180px 1fr; gap: 8px 14px; }
    dt { font-weight: 700; color: #374151; }
    dd { margin: 0; }
  </style>
</head>
<body>
  <main>
    <h1>${escapeHtml(row.title || row.creative_id || row.creative_key)}</h1>
    ${imageSource ? `<img src="${escapeHtml(imageSource)}" alt="Creative thumbnail">` : ''}
    <p>${escapeHtml(row.body || '')}</p>
    <dl>
      <dt>Creative ID</dt><dd>${escapeHtml(row.creative_id)}</dd>
      <dt>Winner Score</dt><dd>${escapeHtml(row.creative_winner_score)}</dd>
      <dt>CTR</dt><dd>${escapeHtml(row.ctr)}</dd>
      <dt>ROAS</dt><dd>${escapeHtml(row.purchase_roas)}</dd>
      <dt>CPA</dt><dd>${escapeHtml(row.cost_per_purchase)}</dd>
      <dt>Frequency</dt><dd>${escapeHtml(row.max_frequency)}</dd>
      <dt>Hook Analysis</dt><dd>${escapeHtml(row.hook_analysis)}</dd>
    </dl>
  </main>
</body>
</html>`;

  fs.writeFileSync(filePath, html);
  return filePath;
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function writeSheet(workbook, name, rows) {
  const sheet = XLSX.utils.json_to_sheet(rows.length ? rows : [{ empty: 'No data' }]);
  XLSX.utils.book_append_sheet(workbook, sheet, name);
}

function addCreativeAssetsToAds(adRows, creativeRows) {
  const creativeByKey = new Map(creativeRows.map((row) => [row.creative_key, row]));

  return adRows.map((row) => {
    const creative = creativeByKey.get(getCreativeKey(row)) || {};
    return {
      ...row,
      creative_winner_score: creative.creative_winner_score || 0,
      visual_performance_rank: creative.visual_performance_rank || '',
      reused_creative: creative.reused || 'NO',
      local_thumbnail_path: creative.local_thumbnail_path || '',
      local_preview_path: creative.local_preview_path || '',
      hook_analysis: creative.hook_analysis || '',
    };
  });
}

function exportWorkbook({ allRows, campaignRows, adSetRows, adRows, creativeRows, audienceRows }) {
  const workbook = XLSX.utils.book_new();
  const actionRows = allRows
    .filter((row) => row.decision !== 'WATCH')
    .sort((a, b) => a.decision_priority - b.decision_priority || b.spend - a.spend);
  const comparisonRows = buildCreativePeriodComparison(adRows);
  const topCtrCreatives = [...creativeRows].sort((a, b) => b.ctr - a.ctr || b.creative_winner_score - a.creative_winner_score).slice(0, 50);
  const scalingOpportunities = getScalingOpportunities(adRows);
  const fatigueRows = getFatigueAlerts(adRows, creativeRows);

  writeSheet(workbook, 'Summary', summarizeRows(allRows));
  writeSheet(workbook, 'Campaigns', campaignRows);
  writeSheet(workbook, 'AdSets', adSetRows);
  writeSheet(workbook, 'Ads', adRows);
  writeSheet(workbook, 'Creatives', creativeRows);
  writeSheet(workbook, 'Creative Fatigue', fatigueRows);
  writeSheet(workbook, 'Action Required', actionRows);
  writeSheet(workbook, 'Creative Winners', getCreativeWinners(creativeRows));
  writeSheet(workbook, 'Creative Losers', getCreativeLosers(creativeRows, comparisonRows));
  writeSheet(workbook, 'Scaling Opportunities', scalingOpportunities);
  writeSheet(workbook, 'Fatigue Alerts', fatigueRows);
  writeSheet(workbook, 'Top CTR Creatives', topCtrCreatives);
  writeSheet(workbook, '7d vs 30d Trend', comparisonRows);
  writeSheet(workbook, 'Audience Analysis', audienceRows);
  writeSheet(
    workbook,
    'Placement Analysis',
    audienceRows.filter((row) => row.breakdown_key === 'placement')
  );
  writeSheet(
    workbook,
    'Device Analysis',
    audienceRows.filter((row) => row.breakdown_key === 'device')
  );
  writeSheet(
    workbook,
    'Age Gender Analysis',
    audienceRows.filter((row) => row.breakdown_key === 'age_gender')
  );
  writeSheet(workbook, 'Scaling Audiences', getScalingAudiences(audienceRows));
  writeSheet(workbook, 'Bad Audiences', getBadAudiences(audienceRows));

  XLSX.writeFile(workbook, OUTPUT_FILE);
}

async function main() {
  validateConfig();

  console.log('Hesap adlari cekiliyor...');
  const accountNameMap = await fetchAccountNames(AD_ACCOUNT_IDS, ACCESS_TOKEN);

  const rawByLevel = {
    campaign: [],
    adset: [],
    ad: [],
  };
  const rawBreakdowns = [];

  for (const adAccountId of AD_ACCOUNT_IDS) {
    for (const period of PERIODS) {
      console.log(`${adAccountId} - ${period.label} verileri cekiliyor...`);
      const [campaigns, adsets, ads] = await Promise.all([
        fetchInsights(adAccountId, 'campaign', period),
        fetchInsights(adAccountId, 'adset', period),
        fetchInsights(adAccountId, 'ad', period),
      ]);

      rawByLevel.campaign.push(...campaigns.map((row) => ({ row, period })));
      rawByLevel.adset.push(...adsets.map((row) => ({ row, period })));
      rawByLevel.ad.push(...ads.map((row) => ({ row, period })));
    }

    for (const period of BREAKDOWN_PERIODS) {
      console.log(`${adAccountId} - ${period.label} audience breakdown verileri cekiliyor...`);
      const results = await Promise.allSettled(
        BREAKDOWN_CONFIGS.map((config) => fetchBreakdownInsights(adAccountId, config, period).then((rows) => ({ config, rows })))
      );

      results.forEach((result, index) => {
        const config = BREAKDOWN_CONFIGS[index];

        if (result.status !== 'fulfilled') {
          console.warn(
            `${adAccountId} - ${config.analysisType} breakdown alinamadi: ${
              result.reason.response?.data?.error?.message || result.reason.message
            }`
          );
          return;
        }

        rawBreakdowns.push(...result.value.rows.map((row) => ({ row, period, config: result.value.config })));
      });
    }
  }

  const adIds = rawByLevel.ad.map(({ row }) => row.ad_id);
  console.log(`${new Set(adIds.filter(Boolean)).size} reklam icin creative bilgileri cekiliyor...`);
  const creativeMap = await fetchCreativesForAds(adIds);

  const campaignRows = addDecisions(
    rawByLevel.campaign.map(({ row, period }) => normalizeInsight(row, 'campaign', period, new Map(), accountNameMap))
  );
  const adSetRows = addDecisions(
    rawByLevel.adset.map(({ row, period }) => normalizeInsight(row, 'adset', period, new Map(), accountNameMap))
  );
  const normalizedAdRows = addDecisions(
    rawByLevel.ad.map(({ row, period }) => normalizeInsight(row, 'ad', period, creativeMap, accountNameMap))
  );

  console.log('Creative ranking ve local preview dosyalari olusturuluyor...');
  const rankedCreativeRows = rankCreatives(getCreativeRows(normalizedAdRows));
  const creativeRows = await enrichCreativePreviews(rankedCreativeRows);
  const adRows = addCreativeAssetsToAds(normalizedAdRows, creativeRows);
  const allRows = [...campaignRows, ...adSetRows, ...adRows];
  const audienceRows = enrichAudienceComparison(
    addAudienceDecisions(
      rawBreakdowns.map(({ row, period, config }) => normalizeBreakdownInsight(row, config, period, accountNameMap))
    )
  );

  exportWorkbook({ allRows, campaignRows, adSetRows, adRows, creativeRows, audienceRows });

  console.log(`\nExcel raporu olusturuldu: ${OUTPUT_FILE}`);
  console.log(`Creative preview klasoru: ${PREVIEW_DIR}`);
  console.log(`Audience breakdown satiri: ${audienceRows.length}`);
  console.log('Karar ozeti:');
  console.table(
    ['SCALE', 'WATCH', 'REFRESH_CREATIVE', 'PAUSE'].map((decision) => ({
      decision,
      count: allRows.filter((row) => row.decision === decision).length,
    }))
  );
}

main().catch((error) => {
  console.error('Hata:', error.response?.data || error.message);
  process.exitCode = 1;
});
