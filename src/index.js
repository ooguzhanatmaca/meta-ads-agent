const { fetchCampaignInsights } = require('./metaApi');
const { analyzeCampaigns } = require('./analyzer');
const { exportToExcel } = require('./exporter');

async function main() {
  const rawInsights = await fetchCampaignInsights();
  const analysis = analyzeCampaigns(rawInsights);

  console.log('\nKampanya Insights');
  console.table(analysis.campaigns);

  console.log('\nEn iyi kampanyalar');
  console.table(analysis.bestCampaigns);

  console.log('\nEn kötü kampanyalar');
  console.table(analysis.worstCampaigns);

  exportToExcel(analysis);
  console.log('\nExcel export oluşturuldu: meta-insights.xlsx');
}

main().catch((error) => {
  console.error('Hata:', error.response?.data || error.message);
  process.exitCode = 1;
});
