function toNumber(value, defaultValue = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : defaultValue;
}

function getRoas(purchaseRoas) {
  if (!Array.isArray(purchaseRoas) || purchaseRoas.length === 0) return 0;
  return toNumber(purchaseRoas[0].value, 0);
}

function normalizeCampaign(raw) {
  const spend = toNumber(raw.spend);
  const clicks = toNumber(raw.clicks);
  const impressions = toNumber(raw.impressions);
  const ctr = toNumber(raw.ctr);
  const cpm = toNumber(raw.cpm);
  const roas = getRoas(raw.purchase_roas);

  const score = roas * 50 + ctr * 20 - cpm * 0.1;

  return {
    campaignId: raw.campaign_id,
    campaignName: raw.campaign_name,
    spend,
    clicks,
    impressions,
    ctr,
    cpm,
    roas,
    score,
  };
}

function analyzeCampaigns(rawCampaigns) {
  const normalized = rawCampaigns.map(normalizeCampaign);
  const sorted = [...normalized].sort((a, b) => b.score - a.score);

  return {
    campaigns: normalized,
    bestCampaigns: sorted.slice(0, 5),
    worstCampaigns: sorted.slice(-5).reverse(),
  };
}

module.exports = {
  analyzeCampaigns,
};
