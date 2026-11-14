# Engine sound effects (not shipped)

The engine and `studio.py doctor` expect these 12 files here (short, dry, normalised; mono or stereo MP3):

`click.mp3`, `click-b.mp3`, `glitch-1.mp3`, `glitch-2.mp3`, `impact-bass-1.mp3`, `impact-bass-2.mp3` (keep these short, a ~0.3 s hit),
`key-press.mp3`, `pop.mp3`, `riser.mp3`, `whoosh.mp3`, `whoosh-b.mp3`, `whoosh-cinematic.mp3`.

Make or source them yourself so the licence is yours: generate them with a sound-effects API (e.g. ElevenLabs SFX, billed per second, so announce the cost first), record them, or use a library whose licence allows redistribution.
Pin them with `studio.py assets lock` and share between machines with `studio.py assets push|pull` (your own bucket).
