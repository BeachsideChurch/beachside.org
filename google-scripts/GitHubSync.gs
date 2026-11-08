/** Add as GitHubSync.gs in the existing Google Apps Script project. */
var BSC_GITHUB = {
  owner: 'BeachsideChurch',
  repo: 'beachside.org',
  branch: 'main',
  workflow: 'sync-drive-content.yml',
  api: 'https://api.github.com',
  version: '2026-03-10'
};

/** Menu handler: select a named weekly folder without typing an ID. */
function runStep4SyncToGitHub() {
  var html = HtmlService.createHtmlOutputFromFile('GitHubSyncDialog')
    .setWidth(700).setHeight(640);
  SpreadsheetApp.getUi().showModalDialog(html, 'Step 4: Sync to GitHub');
}

/** Uses the dated-folder discovery helper already in Transcribe.gs. */
function listGitHubSyncFolders() {
  var props = PropertiesService.getScriptProperties();
  var rootId = bscRequired_(props, 'SERMONS_ROOT_FOLDER_ID');
  if (rootId.indexOf('PASTE_') === 0) {
    throw new Error('Run the existing oneTimeSetup() first.');
  }
  var weeks = collectDatedFolders(DriveApp.getFolderById(rootId));
  weeks.sort(function (a, b) {
    return b.dateStr.localeCompare(a.dateStr) ||
      a.folder.getName().localeCompare(b.folder.getName());
  });
  return weeks.map(function (week) {
    return {id: week.folder.getId(), name: week.folder.getName()};
  });
}

/** Dialog endpoint: recheck that the ID belongs to our sermon folders. */
function requestGitHubFolderSync(folderId, dryRun) {
  var id = bscFolderId_(folderId);
  var allowed = listGitHubSyncFolders().some(function (folder) {
    return folder.id === id;
  });
  if (!allowed) {
    throw new Error('Folder no longer available. Refresh the folder list.');
  }
  return triggerGitHubSync(id, dryRun);
}

/** Callable by other scripts; omitted dryRun defaults to preview. */
function triggerGitHubSync(folderId, dryRun) {
  if (dryRun === undefined) dryRun = true;
  if (typeof dryRun !== 'boolean') {
    throw new Error('dryRun must be true or false, not a string.');
  }
  var id = bscFolderId_(folderId);
  bscCheckFolder_(id);
  // Acquire after prompts: UI dialogs suspend Apps Script execution.
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) {
    throw new Error('Another sync request is in progress. Try again.');
  }
  try {
    var token = bscInstallationToken_();
    var path = '/repos/' + BSC_GITHUB.owner + '/' + BSC_GITHUB.repo +
      '/actions/workflows/' + BSC_GITHUB.workflow + '/dispatches';
    var dispatched = bscRequest_(path, token, {
      ref: BSC_GITHUB.branch,
      inputs: {folder_id: id, dry_run: dryRun, all_folders: true}
    });
    var run = bscParseJson_(dispatched.text);
    var workflowUrl = 'https://github.com/' + BSC_GITHUB.owner + '/' +
      BSC_GITHUB.repo + '/actions/workflows/' + BSC_GITHUB.workflow;
    var runPrefix = 'https://github.com/' + BSC_GITHUB.owner + '/' +
      BSC_GITHUB.repo + '/actions/runs/';
    var url = run && typeof run.html_url === 'string' &&
      run.html_url.indexOf(runPrefix) === 0 ? run.html_url : workflowUrl;
    var runId = run && run.workflow_run_id;
    if (!runId && url.indexOf(runPrefix) === 0) {
      runId = url.slice(runPrefix.length).split('/')[0];
    }
    return {requested: true, dryRun: dryRun, url: url,
      runId: /^\d+$/.test(String(runId)) ? String(runId) : ''};
  } finally {
    lock.releaseLock();
  }
}

function bscInstallationToken_() {
  var props = PropertiesService.getScriptProperties();
  var appId = bscRequired_(props, 'GITHUB_APP_ID');
  var installId = bscRequired_(props, 'GITHUB_INSTALLATION_ID');
  var pem = bscRequired_(props, 'GITHUB_APP_PRIVATE_KEY');
  if (!/^\d+$/.test(appId) || !/^\d+$/.test(installId)) {
    throw new Error('App ID and Installation ID must be numeric.');
  }
  var auth = bscRequest_('/app/installations/' + installId +
    '/access_tokens', bscJwt_(appId, pem), {
      repositories: [BSC_GITHUB.repo], permissions: {actions: 'write'}
    });
  var tokenData = bscParseJson_(auth.text);
  if (!tokenData || !tokenData.token) {
    throw new Error('GitHub did not return an installation token.');
  }
  return tokenData.token;
}

/** Called repeatedly by the dialog, with no server-side sleep. */
function getGitHubSyncProgress(runId) {
  if (!/^\d+$/.test(String(runId))) throw new Error('Invalid GitHub run ID.');
  var token = bscInstallationToken_();
  var base = '/repos/' + BSC_GITHUB.owner + '/' + BSC_GITHUB.repo;
  var runPath = base + '/actions/runs/' + runId;
  var run = bscParseJson_(bscRequest_(runPath, token, null, 'get').text);
  if (!run || String(run.path).split('@')[0] !==
      '.github/workflows/' + BSC_GITHUB.workflow) {
    throw new Error('The run does not belong to the content sync workflow.');
  }
  var result = {done: run.status === 'completed', status: run.status,
    conclusion: run.conclusion || '', log: '', logsPending: false};
  var jobsPath = runPath + '/attempts/' + run.run_attempt + '/jobs?per_page=100';
  var jobsData = bscParseJson_(bscRequest_(jobsPath, token, null, 'get').text);
  var jobs = jobsData && jobsData.jobs || [];
  var job = jobs.filter(function (item) { return item.name === 'sync'; })[0];
  if (!job) {
    if (result.done) result.log = 'The sync job did not start. Check GitHub Actions.';
    return result;
  }
  var steps = job.steps || [];
  var active = steps.filter(function (step) { return step.status === 'in_progress'; })[0];
  if (active) result.status = 'Running ' + active.name;
  if (!result.done) return result;
  var target = steps.filter(function (step) {
    return step.name === 'Read and validate Drive content';
  })[0];
  if (!target || target.conclusion === 'skipped') {
    var failedStep = steps.filter(function (step) {
      return step.conclusion === 'failure';
    })[0];
    result.log = 'Read and validate Drive content did not run.' +
      (failedStep ? '\nFailed step: ' + failedStep.name : '');
    return result;
  }
  var logPath = base + '/actions/jobs/' + job.id +
    '/steps/' + target.number + '/logs';
  var logResponse = bscDownloadLog_(logPath, token);
  var text = logResponse.text;
  if (logResponse.status !== 200) {
    var jobLogPath = base + '/actions/jobs/' + job.id + '/logs';
    var jobLog = bscDownloadLog_(jobLogPath, token);
    if (jobLog.status === 200) {
      text = jobLog.text;
    } else {
      result.logsPending = true;
      result.logNotice = 'Step log HTTP ' + logResponse.status +
        '; complete job log HTTP ' + jobLog.status + '.';
      return result;
    }
  }
  result.log = bscValidationOutput_(text);
  if (result.log.length > 50000) {
    result.log = result.log.slice(0, 50000) + '\n[More output in GitHub Actions]';
  }
  return result;
}

function bscDownloadLog_(path, token) {
  var response = bscRequest_(path, token, null, 'get', true);
  if (response.status === 404 || response.status === 410) return response;
  if (response.status === 302) {
    var headers = response.headers;
    var locationKey = Object.keys(headers).filter(function (key) {
      return key.toLowerCase() === 'location';
    })[0];
    var location = String(headers[locationKey] || '');
    if (!/^https:\/\//.test(location)) throw new Error('Invalid log download URL.');
    // GitHub's signed storage URL authenticates the download itself.
    var download = UrlFetchApp.fetch(location, {
      method: 'get', muteHttpExceptions: true, followRedirects: true
    });
    return {status: download.getResponseCode(), text: download.getContentText()};
  }
  return response;
}

/** Keep script output between the command preamble and subsequent job steps. */
function bscValidationOutput_(text) {
  var cleanText = text.replace(/\u001b\[[0-9;]*m/g, '')
    .replace(/^\d{4}-\d{2}-\d{2}T[\d:.]+Z[ \t]?/gm, '');
  var lines = cleanText.split(/\r?\n/);
  var commandStart = lines.findIndex(function (line) {
    return /##\[group\]Run args=\(\)\s*$/.test(line);
  });
  var start = 0;
  if (commandStart !== -1) {
    start = commandStart + 1;
    while (start < lines.length && lines[start].indexOf('##[endgroup]') === -1) start++;
    if (start === lines.length) {
      return 'Validation output is unavailable. Open GitHub Actions for details.';
    }
    start++;
  } else if (cleanText.indexOf('##[group]') !== -1) {
    return 'Validation output could not be isolated. Open GitHub Actions for details.';
  }
  var end = start;
  var nextStep = /^(?:##\[group\]|Post job cleanup\.|Cleaning up orphan processes)/;
  while (end < lines.length && !nextStep.test(lines[end])) end++;
  return lines.slice(start, end).join('\n').trim() ||
    'The validation step produced no output.';
}

function bscRequired_(props, name) {
  var value = String(props.getProperty(name) || '').trim();
  if (!value) throw new Error('Missing Script Property: ' + name);
  return value;
}

function bscFolderId_(value) {
  var text = String(value || '').trim();
  var pattern = '^https://drive\\.google\\.com/drive/' +
    '(?:u/\\d+/)?folders/([A-Za-z0-9_-]+)(?:[/?#].*)?$';
  var match = new RegExp(pattern).exec(text);
  var id = match ? match[1] : text;
  if (!/^[A-Za-z0-9_-]+$/.test(id)) {
    throw new Error('Enter a Drive folder ID or a Drive folder URL.');
  }
  return id;
}

function bscCheckFolder_(id) {
  var folder;
  try { folder = DriveApp.getFolderById(id); }
  catch (e) { throw new Error('Folder not found or not accessible.'); }
  var counts = {watch: 0, guide: 0, image: 0};
  var files = folder.getFiles();
  while (files.hasNext()) {
    var file = files.next();
    var name = file.getName();
    var kind = /^Watch - .+\.md$/.test(name) ? 'watch' :
      /^Guide - .+\.md$/.test(name) ? 'guide' :
      /\.jpe?g$/i.test(name) ? 'image' : '';
    if (!kind) continue;
    if (file.getMimeType().indexOf('application/vnd.google-apps.') === 0) {
      throw new Error('Upload real Markdown/JPEG files, not Google Docs.');
    }
    counts[kind]++;
  }
  if (counts.watch !== 1 || counts.guide !== 1 || counts.image !== 1) {
    throw new Error('Select one weekly folder containing exactly one ' +
      'Watch .md, one Guide .md, and one JPG/JPEG.');
  }
  return folder;
}

function bscJwt_(appId, pem) {
  var signingKey = bscSigningKey_(pem);
  var now = Math.floor(Date.now() / 1000);
  var header = bscBase64Url_(JSON.stringify({alg: 'RS256', typ: 'JWT'}));
  var claims = bscBase64Url_(JSON.stringify({
    iss: String(appId), iat: now - 60, exp: now + 300
  }));
  var data = header + '.' + claims;
  var signature;
  try {
    signature = Utilities.computeRsaSha256Signature(data, signingKey);
  } catch (e) {
    throw new Error('Private-key signing failed. Check the complete PEM ' +
      'text, BEGIN/END lines, and RSA key format.');
  }
  return data + '.' + bscBase64Url_(signature);
}

/** GitHub downloads PKCS#1. Normalize to PKCS#8 for Google's signer. */
function bscSigningKey_(pem) {
  var text = String(pem || '').replace(/\\n/g, '\n').trim();
  var match = /^-----BEGIN (RSA PRIVATE KEY|PRIVATE KEY)-----\s*([\s\S]*?)\s*-----END \1-----$/
    .exec(text);
  if (!match) {
    throw new Error('GITHUB_APP_PRIVATE_KEY must contain the full PEM ' +
      'private key, including matching BEGIN/END lines.');
  }
  var base64 = match[2].replace(/\s/g, '');
  if (!base64 || !/^[A-Za-z0-9+/]+={0,2}$/.test(base64)) {
    throw new Error('The PEM private-key body contains invalid characters.');
  }
  var bytes;
  try {
    bytes = Utilities.base64Decode(base64).map(function (value) {
      return value & 255;
    });
  } catch (e) {
    throw new Error('The PEM private-key body is not valid Base64.');
  }
  if (bytes.length < 100 || bytes[0] !== 48) {
    throw new Error('The PEM private-key data is incomplete or invalid.');
  }
  if (match[1] === 'RSA PRIVATE KEY') {
    // PrivateKeyInfo: version 0, rsaEncryption AlgorithmIdentifier,
    // then an OCTET STRING containing the original PKCS#1 DER bytes.
    var rsaAlgorithm = [48, 13, 6, 9, 42, 134, 72, 134,
      247, 13, 1, 1, 1, 5, 0];
    var octetString = [4].concat(bscDerLength_(bytes.length), bytes);
    var body = [2, 1, 0].concat(rsaAlgorithm, octetString);
    bytes = [48].concat(bscDerLength_(body.length), body);
  }
  var signedBytes = bytes.map(function (value) {
    return value > 127 ? value - 256 : value;
  });
  var encoded = Utilities.base64Encode(signedBytes);
  return '-----BEGIN PRIVATE KEY-----\n' +
    encoded.match(/.{1,64}/g).join('\n') +
    '\n-----END PRIVATE KEY-----';
}

function bscDerLength_(length) {
  if (length < 128) return [length];
  var bytes = [];
  while (length > 0) {
    bytes.unshift(length & 255);
    length = Math.floor(length / 256);
  }
  return [128 + bytes.length].concat(bytes);
}

function bscBase64Url_(value) {
  return Utilities.base64EncodeWebSafe(value).replace(/=+$/, '');
}

function bscRequest_(path, bearer, body, method, logRequest) {
  var response;
  try {
    response = UrlFetchApp.fetch(BSC_GITHUB.api + path, {
      method: method || 'post', contentType: 'application/json',
      headers: {Authorization: 'Bearer ' + bearer,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': BSC_GITHUB.version},
      payload: body == null ? undefined : JSON.stringify(body), muteHttpExceptions: true,
      followRedirects: false
    });
  } catch (e) {
    throw new Error('GitHub request could not be completed. Check Actions ' +
      'before retrying; a dispatch may already have been accepted.');
  }
  var status = response.getResponseCode();
  var allowedLogStatus = logRequest && [302, 404, 410].indexOf(status) !== -1;
  if (!allowedLogStatus && (status < 200 || status >= 300)) {
    // Do not include response bodies, JWTs, keys, or tokens in errors.
    throw new Error('GitHub HTTP ' + status + '. Check app credentials, ' +
      'installation access, permissions, workflow file, and branch.');
  }
  return {status: status, text: response.getContentText(),
    headers: logRequest ? response.getHeaders() : {}};
}

function bscParseJson_(text) {
  try { return text ? JSON.parse(text) : null; }
  catch (e) { return null; }
}
