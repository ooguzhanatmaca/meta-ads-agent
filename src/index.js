const { fetchAllInsights } = require('./metaApi');
const { analyzeCampaigns } = require('./analyzer');
const { exportToExcel } = require('./exporter');

async function main() {
  const accountInsights = await fetchAllInsights();
  const rawCampaigns = accountInsights.flatMap((account) => account.campaigns);
  const rawAdsets = accountInsights.flatMap((account) => account.adsets);
  const rawAds = accountInsights.flatMap((account) => account.ads);
  const analysis = {
    ...analyzeCampaigns(rawCampaigns),
    adsets: rawAdsets,
    ads: rawAds,
  };

  console.log('\nKampanya Insights');
  console.table(analysis.campaigns);

  console.log('\nEn iyi kampanyalar');
  console.table(analysis.bestCampaigns);

  console.log('\nEn kotu kampanyalar');
  console.table(analysis.worstCampaigns);
  console.log(`\nAdSet satiri: ${rawAdsets.length}`);
  console.log(`Ad satiri: ${rawAds.length}`);

  exportToExcel(analysis);
  console.log('\nExcel export olusturuldu: meta-insights.xlsx');
}

main().catch((error) => {
  console.error('Hata:', error.response?.data || error.message);
  process.exitCode = 1;
});
