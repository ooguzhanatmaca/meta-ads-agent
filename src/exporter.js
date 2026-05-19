const XLSX = require('xlsx');

function exportToExcel({ campaigns, bestCampaigns, worstCampaigns, adsets = [], ads = [] }, filePath = 'meta-insights.xlsx') {
  const workbook = XLSX.utils.book_new();

  const allSheet = XLSX.utils.json_to_sheet(campaigns);
  const bestSheet = XLSX.utils.json_to_sheet(bestCampaigns);
  const worstSheet = XLSX.utils.json_to_sheet(worstCampaigns);
  const adsetsSheet = XLSX.utils.json_to_sheet(adsets.length ? adsets : [{ empty: 'No data' }]);
  const adsSheet = XLSX.utils.json_to_sheet(ads.length ? ads : [{ empty: 'No data' }]);

  XLSX.utils.book_append_sheet(workbook, allSheet, 'All Campaigns');
  XLSX.utils.book_append_sheet(workbook, bestSheet, 'Best Campaigns');
  XLSX.utils.book_append_sheet(workbook, worstSheet, 'Worst Campaigns');
  XLSX.utils.book_append_sheet(workbook, adsetsSheet, 'AdSets');
  XLSX.utils.book_append_sheet(workbook, adsSheet, 'Ads');

  XLSX.writeFile(workbook, filePath);
}

module.exports = {
  exportToExcel,
};
