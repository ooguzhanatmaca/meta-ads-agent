const axios = require('axios');
const XLSX = require('xlsx');
const { fetchAccountNames } = require('../metaAccounts');

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
  'cpc',
  'cpm',
  'frequency',
  'actions',
  'action_values',
  'purchase_roas',
].join(',');

async function fetchMetrics(accountId, level, datePreset) {
  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const accessToken = process.env.META_ACCESS_TOKEN;
  const rows = [];
  let nextUrl = `https://graph.facebook.com/${apiVersion}/${accountId}/insights`;
  let nextParams = {
    fields: METRIC_FIELDS,
    level,
    date_preset: datePreset,
    access_token: accessToken,
    limit: 500,
  };

  while (nextUrl) {
    const response = await axios.get(nextUrl, { params: nextParams });
    rows.push(...(response.data.data || []));
    nextUrl = response.data.paging?.next || null;
    nextParams = null;
  }

  return rows;
}

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function r2(v) {
  return Math.round(toNum(v) * 100) / 100;
}

function getAction(actions, aliases) {
  if (!Array.isArray(actions)) return 0;
  return actions
    .filter((a) => aliases.includes(a.action_type))
    .reduce((sum, a) => sum + toNum(a.value), 0);
}

function getRoas(purchaseRoas) {
  if (!Array.isArray(purchaseRoas) || purchaseRoas.length === 0) return 0;
  return toNum(purchaseRoas[0].value);
}

function normalizeRow(raw, accountId, accountName) {
  const spend = toNum(raw.spend);
  const purchases = getAction(raw.actions, [
    'purchase',
    'omni_purchase',
    'offsite_conversion.fb_pixel_purchase',
  ]);
  const leads = getAction(raw.actions, [
    'lead',
    'onsite_conversion.lead_grouped',
    'offsite_conversion.fb_pixel_lead',
  ]);
  const roas = getRoas(raw.purchase_roas);

  return {
    ad_account_id: accountId,
    account_name: accountName,
    campaign_id: raw.campaign_id || '',
    campaign_name: raw.campaign_name || '',
    adset_id: raw.adset_id || '',
    adset_name: raw.adset_name || '',
    ad_id: raw.ad_id || '',
    ad_name: raw.ad_name || '',
    spend: r2(spend),
    impressions: toNum(raw.impressions),
    clicks: toNum(raw.clicks),
    ctr: r2(raw.ctr),
    cpc: r2(raw.cpc),
    cpm: r2(raw.cpm),
    frequency: r2(raw.frequency),
    leads,
    purchases,
    roas: r2(roas),
    cost_per_lead: leads > 0 ? r2(spend / leads) : 0,
    cost_per_purchase: purchases > 0 ? r2(spend / purchases) : 0,
  };
}

function flagPerformance(row) {
  const lowCtr = Number(process.env.LOW_CTR || 1);
  const highCpc = Number(process.env.HIGH_CPC || 5);
  const highRoas = Number(process.env.HIGH_ROAS || 3);
  const highSpendNoConv = Number(process.env.HIGH_SPEND_NO_PURCHASE || 50);
  const goodLeadCpa = Number(process.env.LOW_CPA || 50);

  const flags = [];

  if (row.ctr > 0 && row.ctr < lowCtr) flags.push('LOW_CTR');
  if (row.cpc > highCpc && row.purchases === 0) flags.push('HIGH_CPC');
  if (row.spend >= highSpendNoConv && row.purchases === 0 && row.leads === 0) {
    flags.push('NO_CONVERSION');
  }
  if (row.roas >= highRoas && row.purchases > 0) flags.push('GOOD_ROAS');
  if (row.leads > 0 && row.cost_per_lead > 0 && row.cost_per_lead <= goodLeadCpa) {
    flags.push('GOOD_LEAD_COST');
  }

  const hasWarn = flags.some((f) => !f.startsWith('GOOD_'));
  const hasGood = flags.some((f) => f.startsWith('GOOD_'));

  return {
    ...row,
    status: hasWarn ? 'WARN' : hasGood ? 'GOOD' : 'OK',
    flags: flags.join(', '),
  };
}

async function trackPerformance(accountIds, datePreset = 'last_7d') {
  const accountNameMap = await fetchAccountNames(accountIds, process.env.META_ACCESS_TOKEN);
  const results = { campaigns: [], adsets: [], ads: [] };

  for (const accountId of accountIds) {
    const accountName = accountNameMap.get(accountId) || accountId;
    console.log(`  ${accountName} (${accountId}) verileri çekiliyor...`);

    const [campaigns, adsets, ads] = await Promise.all([
      fetchMetrics(accountId, 'campaign', datePreset),
      fetchMetrics(accountId, 'adset', datePreset),
      fetchMetrics(accountId, 'ad', datePreset),
    ]);

    results.campaigns.push(
      ...campaigns.map((r) => flagPerformance(normalizeRow(r, accountId, accountName)))
    );
    results.adsets.push(
      ...adsets.map((r) => flagPerformance(normalizeRow(r, accountId, accountName)))
    );
    results.ads.push(
      ...ads.map((r) => flagPerformance(normalizeRow(r, accountId, accountName)))
    );
  }

  return results;
}

function exportToExcel(results, filePath = 'performance-report.xlsx') {
  const wb = XLSX.utils.book_new();

  const sheet = (rows) =>
    XLSX.utils.json_to_sheet(rows.length ? rows : [{ empty: 'Veri yok' }]);

  XLSX.utils.book_append_sheet(wb, sheet(results.campaigns), 'Campaigns');
  XLSX.utils.book_append_sheet(wb, sheet(results.adsets), 'AdSets');
  XLSX.utils.book_append_sheet(wb, sheet(results.ads), 'Ads');

  XLSX.writeFile(wb, filePath);
}

module.exports = { trackPerformance, exportToExcel, flagPerformance };
