.PHONY: install install-all test demo doctor skills

install:            ## core install (Python CLI + Remotion composer)
	python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd composer && npm install
	.venv/bin/faceless setup

install-all:        ## + browser image host + free local transcription
	.venv/bin/pip install -e ".[all]" && .venv/bin/playwright install chromium

test:
	.venv/bin/pytest -q
	cd composer && npx tsc --noEmit

demo:               ## free offline end-to-end run
	.venv/bin/faceless demo --format short

doctor:
	.venv/bin/faceless doctor

skills:             ## re-mirror skills/ into .claude/skills and .agents/skills
	.venv/bin/faceless skills sync
