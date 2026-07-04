const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

config.server = {
  ...config.server,
  enhanceMiddleware: (middleware, server) => {
    return (req, res, next) => {
      // Intercept the response to prevent COOP/COEP headers from being set
      const originalSetHeader = res.setHeader;
      res.setHeader = function (name, value) {
        if (
          name.toLowerCase() === 'cross-origin-opener-policy' ||
          name.toLowerCase() === 'cross-origin-embedder-policy'
        ) {
          return; // Ignore these headers
        }
        originalSetHeader.call(res, name, value);
      };
      return middleware(req, res, next);
    };
  },
};

module.exports = config;
