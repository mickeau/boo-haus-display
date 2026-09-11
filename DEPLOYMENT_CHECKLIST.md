# Boo Haus Display Deployment Checklist

Use this when updating the Raspberry Pi/e-ink display from the reviewed local
project files. This checklist is guidance only; it does not run any deployment
steps by itself.

## Assumptions

- Local reviewed checkout: `/home/mike/projects/boo_haus_display`
- Pi checkout: `~/boo_haus_display`
- Display service name: `boo-haus-display`
- Optional dashboard service name: `boo-haus-dashboard`

Adjust paths if your Pi uses a different directory.

## Files To Preserve On The Pi

Do not overwrite these private/runtime files unless you intentionally want to
replace local settings or data:

- `.env`
- `boo_haus_config.json`
- `credentials.json`
- `token.json`
- `birthdays.json`
- `display_state.json`
- `news_display_state.json`
- `combined_news_recent.json`
- `news_stories.json`
- `news_summaries.json`
- `headline_summaries_cache.json`
- `*_cache.json`
- `waste_collections.json`
- `logs/`
- `display_images/`
- `backups/`

## Before Copying

Run local checks from `/home/mike/projects/boo_haus_display`:

```bash
python3 test_config_handling.py
python3 test_backup_restore.py
python3 test_fetcher_behaviour.py
python3 test_news_pipeline.py
python3 test_runtime_behaviour.py
python3 test_runtime_edge_cases.py
python3 test_screen_fixtures.py
python3 test_health_check.py
python3 test_service_install_files.py
python3 test_display.py --quick
bash -n install_service.sh quick_start.sh install_all_deps.sh
git diff --check
```

Check that no private file is staged or copied accidentally:

```bash
git status --short
git check-ignore .env boo_haus_config.json credentials.json token.json birthdays.json waste_collections.json
```

## Copy Reviewed Files

Recommended approach: copy source files while excluding private/runtime files.
Run from the local machine, replacing `<pi-host>` if needed:

```bash
rsync -av --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'boo_haus_config.json' \
  --exclude 'credentials.json' \
  --exclude 'token.json' \
  --exclude 'birthdays.json' \
  --exclude 'display_state.json' \
  --exclude 'news_display_state.json' \
  --exclude 'combined_news_recent.json' \
  --exclude 'news_stories.json' \
  --exclude 'news_summaries.json' \
  --exclude 'headline_summaries_cache.json' \
  --exclude '*_cache.json' \
  --exclude 'waste_collections.json' \
  --exclude 'logs/' \
  --exclude 'display_images/' \
  --exclude 'backups/' \
  /home/mike/projects/boo_haus_display/ \
  <pi-host>:~/boo_haus_display/
```

If copying manually, copy the repo files but leave the preserved files above in
place on the Pi.

## After Copying On The Pi

From `~/boo_haus_display` on the Pi:

```bash
chmod +x install_service.sh quick_start.sh install_all_deps.sh
python3 -m py_compile boo_haus_main.py config.py base_fetcher.py
python3 health_check.py --skip-network
python3 test_display.py --quick
```

Install or refresh dependencies if needed:

```bash
pip3 install --user -r requirements.txt
```

For optional Pi/display integrations:

```bash
pip3 install --user gpiod inky[rpi,example-depends]
pip3 install --user anthropic
pip3 install --user google-auth-httplib2 google-auth-oauthlib google-api-python-client
```

Install/update service files without starting immediately:

```bash
sudo ./install_service.sh --dashboard --no-start
```

Use `--dashboard` only if you want the dashboard service installed.

## Restart Services

When checks pass:

```bash
sudo systemctl daemon-reload
sudo systemctl restart boo-haus-display
sudo systemctl status boo-haus-display
```

If using the dashboard:

```bash
sudo systemctl restart boo-haus-dashboard
sudo systemctl status boo-haus-dashboard
```

## Verify After Restart

```bash
sudo journalctl -u boo-haus-display -n 80 --no-pager
python3 health_check.py --skip-network --json
ls -lht display_images/ | head
```

Optional live source checks:

```bash
python3 weather_fetcher.py
python3 bin_collections.py
python3 tide_times.py
python3 news_scraper.py
python3 news_summariser.py
```

`news_summariser.py` requires `ANTHROPIC_API_KEY`. Google Calendar requires
`credentials.json`, `token.json`, and configured calendar IDs.

## Rollback

Before deployment, keep a copy of the old Pi checkout or make a backup:

```bash
python3 backup_restore.py --backup --include-logs
```

To restore app config/data from a backup, test first:

```bash
python3 backup_restore.py --restore backups/<backup-file>.tar.gz --dry-run
python3 backup_restore.py --restore backups/<backup-file>.tar.gz
```
