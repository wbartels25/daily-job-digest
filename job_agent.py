name: Daily Job Digest

# Runs every day at 12:00 UTC (~7am Central). Adjust the cron as you like.
# cron format: minute hour day month weekday
on:
  schedule:
    - cron: "0 12 * * *"
  workflow_dispatch: {}   # lets you trigger a run manually from the Actions tab

permissions:
  contents: write          # needed so the agent can commit seen_jobs.json

jobs:
  run-agent:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Run job agent
        env:
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          SENDGRID_API_KEY: ${{ secrets.SENDGRID_API_KEY }}
        run: python job_agent.py

      - name: Persist seen-jobs memory
        run: |
          git config user.name "job-agent"
          git config user.email "actions@github.com"
          git add seen_jobs.json || true
          git commit -m "Update seen jobs $(date -u +%F)" || echo "nothing to commit"
          git push || echo "nothing to push"
