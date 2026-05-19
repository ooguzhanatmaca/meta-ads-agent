const fs = require('fs');

const DEFAULTS = {
  lowCtr: Number(process.env.LOW_CTR || 1),
  highCpc: Number(process.env.HIGH_CPC || 5),
  highRoas: Number(process.env.HIGH_ROAS || 3),
  goodLeadCpa: Number(process.env.LOW_CPA || 50),
  highSpendNoConv: Number(process.env.HIGH_SPEND_NO_PURCHASE || 100),
  minDataSpend: Number(process.env.MIN_DATA_SPEND || 20),
};

function baseFields(row, level) {
  return {
    level,
    ad_account_id: row.ad_account_id,
    account_name: row.account_name,
    entity_id: level === 'campaign' ? row.campaign_id
              : level === 'adset'   ? row.adset_id
              : row.ad_id,
    entity_name: level === 'campaign' ? row.campaign_name
                : level === 'adset'   ? row.adset_name
                : row.ad_name,
    spend: row.spend,
    roas: row.roas,
    ctr: row.ctr,
    cpc: row.cpc,
    leads: row.leads,
    purchases: row.purchases,
    cost_per_lead: row.cost_per_lead,
    cost_per_purchase: row.cost_per_purchase,
    flags: row.flags || '',
  };
}

function rec(base, action, changePct, reason) {
  return { ...base, action, change_percent: changePct, reason };
}

function recommendRow(row, level) {
  const base = baseFields(row, level);
  const t = DEFAULTS;

  // Yeterli veri yoksa karar verme
  if (row.spend < t.minDataSpend) {
    return rec(base, 'WAIT', 0, `Harcama ${row.spend} TL, karar için yeterli veri bekleniyor (min ${t.minDataSpend} TL).`);
  }

  // Yüksek harcama, sıfır dönüşüm → durdur
  if (row.spend >= t.highSpendNoConv && row.purchases === 0 && row.leads === 0) {
    return rec(base, 'PAUSE', -100, `${row.spend} TL harcama var, hiç dönüşüm yok. Durdurma önerilir.`);
  }

  // İyi ROAS → %20 artır
  if (row.roas >= t.highRoas && row.purchases > 0) {
    return rec(base, 'INCREASE', 20, `ROAS ${row.roas} >= ${t.highRoas}. Bütçe %20 artırma önerilir.`);
  }

  // Uygun lead maliyeti → %20 artır
  if (row.leads > 0 && row.cost_per_lead > 0 && row.cost_per_lead <= t.goodLeadCpa) {
    return rec(base, 'INCREASE', 20, `Lead maliyeti ${row.cost_per_lead} TL uygun (eşik: ${t.goodLeadCpa} TL). Bütçe %20 artırma önerilir.`);
  }

  // Düşük CTR → %20 azalt
  if (row.ctr > 0 && row.ctr < t.lowCtr) {
    return rec(base, 'DECREASE', -20, `CTR ${row.ctr}% düşük (eşik: ${t.lowCtr}%). Bütçe %20 azaltma önerilir.`);
  }

  // Yüksek CPC, dönüşüm yok → %20 azalt
  if (row.cpc > t.highCpc && row.purchases === 0 && row.leads === 0) {
    return rec(base, 'DECREASE', -20, `CPC ${row.cpc} TL yüksek (eşik: ${t.highCpc} TL), dönüşüm yok. Bütçe %20 azaltma önerilir.`);
  }

  return rec(base, 'WATCH', 0, 'Performans normal. İzlemeye devam et.');
}

function recommend(rows, level) {
  return rows.map((row) => recommendRow(row, level));
}

function saveRecommendations(recommendations, filePath = 'recommendations.json') {
  fs.writeFileSync(filePath, JSON.stringify(recommendations, null, 2), 'utf8');
}

function loadRecommendations(filePath = 'recommendations.json') {
  if (!fs.existsSync(filePath)) return [];
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

module.exports = { recommend, saveRecommendations, loadRecommendations };
