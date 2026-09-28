// app.config.js — extends app.json with values that must not be committed.
//
// google-services.json (Firebase config, required for Android push) is kept
// out of git. Locally, drop it next to this file; on EAS, upload it as a file
// environment variable named GOOGLE_SERVICES_JSON.
const fs = require('fs');
const path = require('path');

module.exports = ({ config }) => {
  const localFile = path.join(__dirname, 'google-services.json');
  const googleServicesFile = process.env.GOOGLE_SERVICES_JSON
    || (fs.existsSync(localFile) ? './google-services.json' : undefined);

  return {
    ...config,
    android: {
      ...config.android,
      ...(googleServicesFile ? { googleServicesFile } : {}),
    },
  };
};
