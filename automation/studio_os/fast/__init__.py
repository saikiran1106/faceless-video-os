"""Fast media pipeline: UI only for the one protected action (submit), site data APIs for the rest.

  storyboards: N parallel ChatGPT tabs, completion + download via ChatGPT's conversation API
  clips:       upload all frames once, submit every Flow job back-to-back, harvest via Flow's media API

Generation requests on both sites are protected (ChatGPT sentinel tokens, Flow reCAPTCHA). We never
mint or replay those tokens; a real click submits each job. See docs/tech-reels/FAST_PIPELINE.md.
"""
