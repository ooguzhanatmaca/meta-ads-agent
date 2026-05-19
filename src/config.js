const dotenv = require('dotenv');
const { parseAdAccountIds } = require('./metaAccounts');

dotenv.config();

const adAccountIds = parseAdAccountIds();

module.exports = {
  accessToken: process.env.META_ACCESS_TOKEN,
  adAccountId: adAccountIds[0],
  adAccountIds,
  apiVersion: process.env.META_API_VERSION || 'v21.0',
  datePreset: process.env.META_DATE_PRESET || 'last_7d',
};
