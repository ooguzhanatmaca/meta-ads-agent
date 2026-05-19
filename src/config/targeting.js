const COUNTRY_PRESETS = {
  turkiye: ['TR'],
  avrupa_turk: ['DE', 'NL', 'BE', 'FR', 'AT', 'CH', 'GB'],
  avrupa_toptan: ['DE', 'NL', 'BE', 'FR', 'IT', 'ES', 'GB'],
  korfez: ['AE', 'SA', 'QA', 'KW', 'BH', 'OM'],
  global_test: ['TR', 'DE', 'NL', 'BE', 'FR', 'GB', 'AE'],
};

const PRESET_LABELS = {
  turkiye: 'Türkiye',
  avrupa_turk: 'Avrupa Türk Nüfusu (DE,NL,BE,FR,AT,CH,GB)',
  avrupa_toptan: 'Avrupa Toptan Pazar (DE,NL,BE,FR,IT,ES,GB)',
  korfez: 'Körfez Ülkeleri (AE,SA,QA,KW,BH,OM)',
  global_test: 'Global Test (TR,DE,NL,BE,FR,GB,AE)',
};

// Essenceoflife için varsayılan ilgi alanları (ID bulmak için search-interests.js kullanın)
const ESSENCE_DEFAULT_INTERESTS_HINT = [
  'butik',
  'kadın giyim',
  'toptan giyim',
  'moda mağazası',
  'e-ticaret',
];

function getCountries(env = process.env) {
  if (env.TARGET_COUNTRIES) {
    return env.TARGET_COUNTRIES.split(',').map((c) => c.trim()).filter(Boolean);
  }
  const preset = env.DEFAULT_TARGETING_PRESET || 'turkiye';
  return COUNTRY_PRESETS[preset] || ['TR'];
}

function getPresetLabel(env = process.env) {
  if (env.TARGET_COUNTRIES) {
    return `Özel (${env.TARGET_COUNTRIES})`;
  }
  const preset = env.DEFAULT_TARGETING_PRESET || 'turkiye';
  return PRESET_LABELS[preset] || preset;
}

function getInterests(env = process.env) {
  const raw = env.ESSENCE_INTEREST_IDS || '';
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((id) => ({ id }));
}

function buildTargeting(overrides = {}, env = process.env) {
  const countries = overrides.countries || getCountries(env);
  const ageMin = overrides.age_min || Number(env.DEFAULT_AGE_MIN || 24);
  const ageMax = overrides.age_max || Number(env.DEFAULT_AGE_MAX || 50);
  const interests = overrides.interests !== undefined ? overrides.interests : getInterests(env);

  const targeting = {
    age_min: ageMin,
    age_max: ageMax,
    geo_locations: { countries },
  };

  if (overrides.genders && overrides.genders.length > 0) {
    targeting.genders = overrides.genders;
  }

  if (interests.length > 0) {
    targeting.flexible_spec = [{ interests }];
  }

  return targeting;
}

module.exports = {
  COUNTRY_PRESETS,
  PRESET_LABELS,
  ESSENCE_DEFAULT_INTERESTS_HINT,
  getCountries,
  getPresetLabel,
  getInterests,
  buildTargeting,
};
