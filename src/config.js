const dotenv = require('dotenv');

dotenv.config();

module.exports = {
  accessToken: process.env.META_ACCESS_TOKEN,
  adAccountId: process.env.META_AD_ACCOUNT_ID,
  apiVersion: process.env.META_API_VERSION || 'v21.0',
  datePreset: process.env.META_DATE_PRESET || 'last_7d',
};
