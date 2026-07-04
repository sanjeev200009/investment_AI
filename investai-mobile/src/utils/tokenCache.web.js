// Web implementation — expo-secure-store is native-only, use localStorage instead
const tokenCache = {
  async getToken(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  async saveToken(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // noop
    }
  },
};

export default tokenCache;
