# Keyframes by hand (any image tool or a designer)

```bash
faceless images jobs <p>
faceless images prompts <p>       # writes 07-keyframes/PROMPTS.md: one block per frame + refs to attach
```
1. Generate ONE image per block in your tool of choice (Midjourney, Gemini, Leonardo, Firefly, ...),
   at the aspect the block asks for, attaching the listed reference images.
2. Save each image with the exact name in the block header (`KF001.png`, `KF002.png`, ...).
   Put them in a folder and run `faceless images ingest <p> <folder>` - only exact id names are
   filed; anything else is listed as skipped, never guessed.
   Or file one at a time after looking at it: `faceless images record <p> KF001 ~/Downloads/img.png`.
3. `faceless images manifest <p>` → `faceless review contact-sheet <p>` → QA → complete.
