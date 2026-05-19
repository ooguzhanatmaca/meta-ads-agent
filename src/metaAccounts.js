const axios = require('axios');

function parseAdAccountIds(env = process.env) {
  const multiAccountIds = (env.META_AD_ACCOUNT_IDS || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  if (multiAccountIds.length > 0) {
    return [...new Set(multiAccountIds)];
  }

  return env.META_AD_ACCOUNT_ID ? [env.META_AD_ACCOUNT_ID.trim()].filter(Boolean) : [];
}

async function fetchAccountNames(accountIds, accessToken) {
  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const results = await Promise.allSettled(
    accountIds.map((id) =>
      axios
        .get(`https://graph.facebook.com/${apiVersion}/${id}`, {
          params: { fields: 'id,name', access_token: accessToken },
        })
        .then((res) => ({ id, name: res.data.name || id }))
    )
  );

  const nameMap = new Map();
  results.forEach((result, index) => {
    const id = accountIds[index];
    nameMap.set(id, result.status === 'fulfilled' ? result.value.name : id);
  });

  return nameMap;
}

module.exports = {
  parseAdAccountIds,
  fetchAccountNames,
};
