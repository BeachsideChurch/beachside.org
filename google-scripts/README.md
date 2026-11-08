# Google Apps Script integration

These files implement Step 4 in the existing Sermon Guide Google Sheet.

1. Add or replace the script file `GitHubSync.gs` in the Sheet's Apps Script project.
2. Add or replace the HTML file `GitHubSyncDialog` using `GitHubSyncDialog.html`.
3. In the existing `Code.gs` `onOpen()` menu, add this item after Step 3.

```javascript
.addItem('4. Sync message files to GitHub', 'runStep4SyncToGitHub')
```

The integration uses the existing `collectDatedFolders()` helper and
`SERMONS_ROOT_FOLDER_ID` Script Property. Configure `GITHUB_APP_ID`,
`GITHUB_INSTALLATION_ID`, and `GITHUB_APP_PRIVATE_KEY` in Apps Script's
Project Settings > Script Properties. The private key value must contain
the complete PEM text, including its matching BEGIN and END lines.

Save and reload the Sheet. Select a weekly folder and run a preview before
publishing. The dialog monitors the GitHub run and displays the sync output.

These repository files are the maintained source. Copy updates into the live
Apps Script project to apply them. The rest of that project's existing scripts
provide the generation and transcription steps.

Keep private keys, access tokens, and service-account JSON credentials in
Apps Script Properties or GitHub Secrets as appropriate. PDFs and temporary
working files are generated under the ignored `output/pdf/` and `tmp/pdfs/`
directories.
