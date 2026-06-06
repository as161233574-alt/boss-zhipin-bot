# Contributing

## Development Setup

```bash
git clone https://github.com/longnull-ck/lakejobai-job-radar.git
cd lakejobai-job-radar
pip install -e ".[dev]"
playwright install firefox
```

## Code Style

- Python: follow PEP 8, max line length 120
- HTML/CSS/JS: single file dashboard, keep it readable
- Use `ruff` for linting: `ruff check .`
- No comments unless necessary

## Pull Request Flow

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes and test locally
4. Push and open PR against `main`

## Project Conventions

- All Python code is flat (no src-layout for the main modules)
- CLI module lives in `lakejob_cli/`
- Database migrations are manual ALTER TABLE in `init_db()`
- Frontend is a single HTML file with inline CSS/JS
- API returns JSON, CLI outputs JSON envelope

## Testing

```bash
# Manual testing: start server and use web console
python boss_app.py --port 8010

# CLI testing
lakejob status
lakejob search "AI Agent" --city 北京
```
