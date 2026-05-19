const axios = require('axios');

const CTA_OPTIONS = [
  'LEARN_MORE',
  'SHOP_NOW',
  'CONTACT_US',
  'SIGN_UP',
  'SEND_MESSAGE',
  'WHATSAPP_MESSAGE',
  'GET_QUOTE',
];

async function createCreative({
  accountId,
  name,
  pageId,
  message,
  link,
  linkTitle,
  description,
  imageHash,
  videoId,
  callToAction = 'LEARN_MORE',
}) {
  if (!accountId || !pageId) throw new Error('accountId ve pageId gerekli');
  if (!message) throw new Error('Reklam metni (message) gerekli');

  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const accessToken = process.env.META_ACCESS_TOKEN;

  let storySpec;

  if (videoId) {
    storySpec = {
      page_id: pageId,
      video_data: {
        video_id: videoId,
        message,
        title: linkTitle || '',
        description: description || '',
        call_to_action: {
          type: callToAction,
          value: { link: link || '' },
        },
      },
    };
  } else {
    storySpec = {
      page_id: pageId,
      link_data: {
        message,
        link: link || 'https://www.facebook.com',
        name: linkTitle || '',
        description: description || '',
        call_to_action: {
          type: callToAction,
          value: { link: link || '' },
        },
        ...(imageHash ? { image_hash: imageHash } : {}),
      },
    };
  }

  const params = new URLSearchParams({
    name,
    object_story_spec: JSON.stringify(storySpec),
    access_token: accessToken,
  });

  const response = await axios.post(
    `https://graph.facebook.com/${apiVersion}/${accountId}/adcreatives`,
    params
  );

  return response.data;
}

async function createAd({ accountId, adsetId, name, creativeId }) {
  if (!accountId || !adsetId || !creativeId) {
    throw new Error('accountId, adsetId ve creativeId gerekli');
  }

  const apiVersion = process.env.META_API_VERSION || 'v21.0';
  const accessToken = process.env.META_ACCESS_TOKEN;

  const params = new URLSearchParams({
    name,
    adset_id: adsetId,
    creative: JSON.stringify({ creative_id: creativeId }),
    status: 'PAUSED',
    access_token: accessToken,
  });

  const response = await axios.post(
    `https://graph.facebook.com/${apiVersion}/${accountId}/ads`,
    params
  );

  return response.data;
}

module.exports = { createCreative, createAd, CTA_OPTIONS };
