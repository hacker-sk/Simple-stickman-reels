# Flow batch images

GitHub Actions run: Chrome + ZAPI Flow extension on Google Flow, prompts from prompts/batch.json, downloads uploaded to Google Drive.

## One-time setup
1. The ZAPI Flow extension (Chrome Web Store id debadkiomlbdambamdpdlgdkgnedcjil) is downloaded automatically at the start of each run. To pin a version instead, commit the unpacked folder (without _metadata) to flow-batch/extension/zapi-flow.
2. On your own computer: cd flow-batch, npm install, npx playwright install chromium, node save_login.js. Log in, press Enter. Copy flow_cookies_b64.txt into repo secret FLOW_COOKIES_B64.
3. Create an rclone Drive remote named gdrive (rclone config), then copy rclone.conf contents into secret RCLONE_CONF.
4. In Flow, open or create a project and copy its URL into repo variable FLOW_PROJECT_URL (the extension only works inside an open project).
5. Optional repo variable DRIVE_FOLDER (default FlowBatch).

## Run
Actions > Flow Batch Images > Run workflow, or wait for the daily schedule. Edit prompts/batch.json to change the batch (one prompt per entry).

## Tuning
config.json holds the selectors, the done text and timeouts. Screenshots of each step are uploaded as the flow-batch-output artifact.
