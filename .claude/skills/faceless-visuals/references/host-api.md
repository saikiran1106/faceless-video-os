# Keyframes via the OpenAI Images API (`api` host)

Hands-off, paid per image. Needs `OPENAI_API_KEY`.

```bash
faceless images jobs <p>
faceless images generate <p>              # prints count + estimated and worst-case USD, spends nothing
faceless images generate <p> --limit 1 --yes   # do ONE first, look at it, check the cost
faceless images generate <p> --yes        # the rest
```
- Model/quality: `FACELESS_OPENAI_IMAGE_MODEL` (default `gpt-image-1`), `FACELESS_OPENAI_IMAGE_QUALITY` (`low|medium|high`, default `medium`).
- Jobs with `reference_paths` go through the edits endpoint so references steer identity.
- Already-generated frames are skipped on re-runs. Regenerate one: delete its PNG in `07-keyframes/images/`, then `--only KF007 --yes`.
- Every call is recorded against the project budget; the run stops if the budget would be exceeded.
