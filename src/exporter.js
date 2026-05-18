const XLSX = require('xlsx');

function exportToExcel({ campaigns, bestCampaigns, worstCampaigns }, filePath = 'meta-insights.xlsx') {
  const workbook = XLSX.utils.book_new();

  const allSheet = XLSX.utils.json_to_sheet(campaigns);
  const bestSheet = XLSX.utils.json_to_sheet(bestCampaigns);
  const worstSheet = XLSX.utils.json_to_sheet(worstCampaigns);

  XLSX.utils.book_append_sheet(workbook, allSheet, 'All Campaigns');
  XLSX.utils.book_append_sheet(workbook, bestSheet, 'Best Campaigns');
  XLSX.utils.book_append_sheet(workbook, worstSheet, 'Worst Campaigns');

  XLSX.writeFile(workbook, filePath);
}

module.exports = {
  exportToExcel,
};
