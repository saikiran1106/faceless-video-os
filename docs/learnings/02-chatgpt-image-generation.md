# 2. ChatGPT image generation from an agent

Used when the host has no built-in image tool (Claude Code) or the built-in tool hits plan limits fast (Codex CLI image
generation hit ChatGPT plan limits quickly; the browser route has been more sustainable). Code: `automation/studio_os/browser`
(resumable job store, runner, adapter) and `automation/studio_os/fast` (parallel tabs, API-read completion, JSON batch).

## Rules that prevent the expensive mistakes

1. **Generate inside one ChatGPT *Project*, never in loose chats.** The project carries the seeded character/style sheets;
   a loose chat has no authority images and drifts, and later nobody can find the batch. The adapter refuses to run on a URL
   that is not the project or a conversation inside it.
2. **One image per message.** Never position-bind a multi-image answer. ChatGPT drops entries, reorders, merges into a collage.
3. **Bind by content, never by filename or order.** A frame belongs to the beat whose prompt produced it: the beat id is in the
   prompt tag, and the binder verifies it. Never recast a frame onto another beat; regenerate that beat instead.
   (`tools/browser/bind_keyframes.py`, `contact_sheet.py`, `detect_grids.py`.)
4. **JSON-batch mode ("N separate images from ONE message") is fast but mis-binds** when duplicate ids shift. Eyeball every
   image against its prompt, or use single-image mode, which binds correctly.
5. **Attachment set governs the whole batch.** Whatever reference images are attached to the message apply to every image in it.
   Don't batch beats that need different references.
6. **Derived queues go stale.** A queue file generated from the beat plan must be rebuilt after the plan changes (hash the plan
   into the queue and fail on mismatch).
7. **Characters: start a fresh chat per character sheet** (`--fresh-chat`). Reusing one chat makes faces converge ("same-face AI").
8. **Reference image beats more words.** When you have the right picture, attach it and spend the prompt on what should change.
9. **Never resubmit on a timeout.** A timed-out generation may still complete; look for it first (free) before paying again.
10. **Ask before any paid fallback** (Images API) and say the minimum and the worst-case cost.

## Speed: use the UI only where the site protects the action

| Action | How | Why |
|---|---|---|
| Send the prompt | Real composer + send button | Protected by sentinel/anti-bot tokens that we never mint or replay |
| Detect the result, bind it, download it | The page's own conversation API from inside the page (`/backend-api/conversation/{id}`, `/backend-api/files/download/{id}`) | An image belongs to the message it answers; no DOM counting, no false "done?" timeouts |

Measured effect on a 15-image reel: ~2 h serial → ~8–12 min with **3 parallel tabs**, API completion detection, 0.8 s chip-remove
and an 18 s page open. Real throughput is bounded by plan rate limits (assume 2–3 tabs).

## Prompting notes

- Keep the **top 30 %** of a frame clean for titles and a **lower-middle band** for captions when frames feed a vertical video.
- **Text in images:** generate the exact text inside ChatGPT's image (thumbnails, covers) with exact strings, colours and sizes in
  the prompt, then check glyphs by eye. For non-Latin scripts models garble conjuncts, so verify every glyph or overlay text in the editor.
- Keep a **plan tag** (beat id + a short hash of the prompt) inside every prompt so the result can always be traced back.
- Cover/thumbnail text must sit inside the **centre crop** that the Instagram profile grid and feed show.

## Content guardrails (two gates)

ChatGPT image generation has a prompt filter **and** an output classifier on the rendered pixels. "The image we created may
violate our guardrails…" is the second one: the prompt passed, the picture was rejected. Practical consequences:
- A negative qualifier ("no gore", "no nudity") next to a description that still produces the flagged pixels changes nothing;
  the *depicted content* is evaluated. Re-describe what is in the frame (name garments, set the crop and camera angle) rather than
  adding disclaimers.
- Classifiers have real false-positive rates on artistic or historical subjects. Treat a reject as a staging problem ("what
  pixels did it see?"), not as a permissions problem. This is for staging legitimate scenes more clearly, never for producing
  disallowed content.
- Never put a minor in a scene that involves force, restraint or injury; keep age out of scene prompts and cut before impact.
- Leave a `guardrail_note` on every entry you fix so a later pass does not restore the original wording.
