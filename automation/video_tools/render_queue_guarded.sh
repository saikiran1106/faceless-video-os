#!/bin/bash
# Usage: COMP=<remotion composition id> [MEDIA_GUARD=path] render_queue_guarded.sh   (run from <project>/compose, expects ./remotion)
# GUARDED (media_guard seal after every chunk; corrupt chunks re-render). Render remaining chapter chunks as soon as every plate they use exists. Usage: render_queue.sh
cd "$(dirname "$0")/remotion"
P=../..
while true; do
  next=$(python3 -I - <<'PY'
import json, os
p=json.load(open('src/plan.json')); have={f[:-4] for f in os.listdir('public/plates')}
ch=p['chapters']+[{'name':'END','from':p['durationInFrames']}]
for i,(a,b) in enumerate(zip(ch,ch[1:])):
    out=f"renders/chunks/{a['name']}.mp4"
    if os.path.exists(out) or os.path.exists(out+'.lock'): continue
    need={s['id'] for s in p['shots'] if s['kind']=='plate' and a['from']<=s['from']<b['from']}
    if need<=have: print(a['name'], 0 if i==0 else a['from'], b['from']-1); break
else:
    print('WAIT' if any(not os.path.exists(f"renders/chunks/{a['name']}.mp4") for a in ch[:-1]) else 'DONE')
PY
)
  [ "$next" = "DONE" ] && break
  if [ "$next" = "WAIT" ]; then $P/07-motion/prep_plates.sh >/dev/null 2>&1; sleep 30; continue; fi
  set -- $next
  if ps -eo args | grep -q "[r]un_json_batch"; then C=2; else C=2; fi
  touch renders/chunks/$1.mp4.lock; S=$(date +%s)
  TMPDIR=${REMOTION_TMPDIR:-$HOME/.cache/remotion-tmp} nice -n 5 npx remotion render src/index.tsx ${COMP:-Film} renders/chunks/$1.tmp.mp4 --frames=$2-$3 --gl=swangle --concurrency=$C --crf=16 --muted --timeout=180000 --log=error > renders/chunks/$1.log 2>&1
  rc=$?; if [ $rc -eq 0 ] && ! python3 -I "${MEDIA_GUARD:-$(dirname "$0")/../tools/media/media_guard.py}" seal renders/chunks/$1.tmp.mp4 >> renders/chunks/guard.log 2>&1; then rc=99; fi  # corrupt chunk -> re-render
  [ $rc -eq 0 ] && mv renders/chunks/$1.tmp.mp4 renders/chunks/$1.mp4 && mv renders/chunks/$1.tmp.mp4.sha256 renders/chunks/$1.mp4.sha256
  rm -f renders/chunks/$1.mp4.lock; echo "$1 exit $rc c=$C $(( $(date +%s)-S ))s" >> renders/chunks/times.txt
  [ $rc -ne 0 ] && sleep 20
done
echo ALL_CHUNKS_DONE >> renders/chunks/times.txt
