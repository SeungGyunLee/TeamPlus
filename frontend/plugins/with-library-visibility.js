const { withAndroidManifest } = require('expo/config-plugins');

module.exports = function withLibraryVisibility(config) {
  return withAndroidManifest(config, next => {
    const manifest = next.modResults.manifest;
    const packageName = 'idoit.slpck.kwangwoon';
    const queries = manifest.queries ??= [];
    if (!queries.some(query => query.package?.some(entry => entry.$['android:name'] === packageName))) {
      queries.push({ package: [{ $: { 'android:name': packageName } }] });
    }
    return next;
  });
};
