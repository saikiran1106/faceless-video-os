# Keyframes on Codex (built-in image tool)

Codex can generate images itself. Use the SAME compiled jobs every other host uses.

1. `faceless images jobs <p>` (and `--sheets` first if the bible has recurring characters).
2. Read `.faceless/image_jobs.json`. Work through jobs **in order, one image per call, sequentially**.
3. For each job:
   - Use `prompt` verbatim. Attach every path in `reference_paths` as an input image when the tool accepts inputs.
   - Ask for the job's `aspect` (9:16 portrait for shorts, 16:9 landscape for long-form).
   - Save the result, then file it against its job:
     `faceless images record <p> <keyframe_id> <saved_file> --host codex`
     The command decodes the image and rejects the wrong aspect.
4. LOOK at each image before moving on. If it does not show the beat's `SHOW:` line, retry once with the failing detail made explicit; after 2 attempts, change the beat's `visual_objective` and recompile.
5. Codex usage is not metered in USD by the CLI. If the human tracks spend, record it: `faceless cost <p> --amount-usd 0 --provider codex-imagegen --operation-id <job_id> --stage keyframes`.
6. `faceless images manifest <p>` → `faceless review contact-sheet <p>` → QA → complete.
