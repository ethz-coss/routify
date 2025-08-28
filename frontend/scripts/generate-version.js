const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function getGitVersion() {
  try {
    return execSync('git rev-parse --short HEAD').toString().trim();
  } catch (e) {
    console.error('Error fetching Git version:', e);
    return 'unknown';
  }
}

const versionInfo = {
  version: require('../package.json').version,
  gitHash: getGitVersion(),
  buildDate: new Date().toISOString(),
};

const filePath = path.join(__dirname, '../src/assets/version.json');
fs.writeFileSync(filePath, JSON.stringify(versionInfo, null, 2));

console.log('Version file generated:', versionInfo);