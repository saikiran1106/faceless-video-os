.PHONY: install install-minimal test demo doctor skills lint

install:            ## everything: system tools, CLI, Remotion, browser host, local transcription
	./install.sh

install-minimal:    ## CLI + Remotion only
	./install.sh --minimal

test:
	.venv/bin/pytest -q
	cd composer && npx tsc --noEmit

lint:
	shellcheck -S warning install.sh

demo:               ## free offline end-to-end run
	.venv/bin/faceless demo --format short

doctor:
	.venv/bin/faceless doctor

skills:             ## re-mirror skills/ into .claude/skills and .agents/skills
	.venv/bin/faceless skills sync
