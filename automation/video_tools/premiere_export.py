"""Premiere Pro importable timeline (FCP7 xmeml v4) + EDL + shot-list CSV, cut at every shot.

usage: premiere_export.py PROJECT_DIR [NAME]

PROJECT_DIR must contain
  plan.json      {"fps":24,"durationInFrames":N,"shots":[{from,dur,kind,name|id|mg,line,trans?}],"chapters":[{name,from}]}
  timeline.json  {"lines":[{"i":0,"text":"..."}]}                     (narration text per shot line, for the shot list)
  out/Media/Video/<NAME>_Picture.mp4    the finished picture, no audio
  out/Media/Audio/{Voice(mono),Music_Score,Ambience_Beds,SFX}.wav   stems, same length as the picture
Writes out/<NAME>_Premiere.xml, out/<NAME>_cuts.edl, out/<NAME>_ShotList.csv.
Media paths are RELATIVE to the xml, so the folder can be zipped and handed over; Fix_Paths.py (same folder) rewrites them
to absolute paths if Premiere reports the media offline. Premiere imports it with File > Import.
"""
import json, csv, sys
from pathlib import Path
from xml.sax.saxutils import escape
R = Path(sys.argv[1]).resolve(); P = R / "out"; NAME = sys.argv[2] if len(sys.argv) > 2 else "Project"
plan = json.load(open(R / "plan.json", encoding="utf-8"))
T = json.load(open(R / "timeline.json", encoding="utf-8"))
FPS, ND = 24, plan["durationInFrames"]
LINE = {l["i"]: l["text"] for l in T["lines"]}
def tc(f): return "%02d:%02d:%02d:%02d" % (f // (3600 * FPS), f // (60 * FPS) % 60, f // FPS % 60, f % FPS)
RATE = f"<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>"
TCODE = f"<timecode>{RATE}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>"

def label(s):
    k = s["kind"]
    if k == "stock": return f"STOCK {s['name']}"
    if k == "plate": return f"AI PLATE {s['id']} ({s.get('move','')})"
    if k == "ref": return f"FOSSIL {s['id']}"
    return f"GRAPHIC {s['mg']}"
def source(s):
    k = s["kind"]
    if k == "stock": return "Library/Stock_footage/" + Path(s["file"]).name
    if k == "plate": return f"Library/AI_plates/{s['id']}.jpg"
    if k == "ref": return f"Library/Fossil_reference/{s['id']}.jpg"
    return "(motion graphic, baked into picture)"

PIC = f"Media/Video/{NAME}_Picture.mp4"
def vfile(first):
    if not first: return '<file id="file-picture"/>'
    return (f'<file id="file-picture"><name>{NAME}_Picture.mp4</name><pathurl>{PIC}</pathurl>{RATE}<duration>{ND}</duration>{TCODE}'
            f'<media><video><samplecharacteristics>{RATE}<width>1920</width><height>1080</height><anamorphic>FALSE</anamorphic>'
            f'<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></video></media></file>')
vclips = []
for n, s in enumerate(plan["shots"]):
    a, b = s["from"], s["from"] + s["dur"]
    vclips.append(f'<clipitem id="clipitem-v{n+1}"><name>{escape("%03d %s" % (n + 1, label(s)))}</name><enabled>TRUE</enabled><duration>{ND}</duration>{RATE}'
                  f'<start>{a}</start><end>{b}</end><in>{a}</in><out>{b}</out>{vfile(n == 0)}'
                  f'<sourcetrack><mediatype>video</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
assert plan["shots"][0]["from"] == 0 and plan["shots"][-1]["from"] + plan["shots"][-1]["dur"] == ND

# audio stems: name, channels
STEMS = [("Voice", 1), ("Music_Score", 2), ("Ambience_Beds", 2), ("SFX", 2)]
def afile(name, ch, first):
    if not first: return f'<file id="file-{name}"/>'
    return (f'<file id="file-{name}"><name>{name}.wav</name><pathurl>Media/Audio/{name}.wav</pathurl>{RATE}<duration>{ND}</duration>{TCODE}'
            f'<media><audio><samplecharacteristics><depth>24</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>{ch}</channelcount></audio></media></file>')
atracks = []; ti = 0
for name, ch in STEMS:
    for c in range(ch):
        ti += 1
        typ = "Mono" if ch == 1 else "Stereo"
        atracks.append(f'<track currentExplodedTrackIndex="{c}" totalExplodedTrackCount="{ch}" premiereTrackType="{typ}">'
                       f'<clipitem id="clipitem-a-{name}-{c+1}" premiereChannelType="{"mono" if ch == 1 else "stereo"}"><name>{name}</name><enabled>TRUE</enabled><duration>{ND}</duration>{RATE}'
                       f'<start>0</start><end>{ND}</end><in>0</in><out>{ND}</out>{afile(name, ch, c == 0)}'
                       f'<sourcetrack><mediatype>audio</mediatype><trackindex>{c+1}</trackindex></sourcetrack></clipitem>'
                       f'<enabled>TRUE</enabled><locked>FALSE</locked></track>')
markers = "".join(f'<marker><name>{escape(c["name"])}</name><comment></comment><in>{c["from"]}</in><out>-1</out></marker>' for c in plan["chapters"])
xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
<sequence id="sequence-1"><name>{NAME}_Final</name><duration>{ND}</duration>{RATE}{TCODE}{markers}
<media>
<video><format><samplecharacteristics>{RATE}<width>1920</width><height>1080</height><anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>
<track>{"".join(vclips)}<enabled>TRUE</enabled><locked>FALSE</locked></track></video>
<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>24</depth><samplerate>48000</samplerate></samplecharacteristics></format>
{"".join(atracks)}</audio>
</media></sequence></xmeml>
'''
(P / f"{NAME}_Premiere.xml").write_text(xml, encoding="utf-8")

# CMX3600 EDL (video cuts only; universal fallback)
ed = [f"TITLE: {NAME}_Final", "FCM: NON-DROP FRAME", ""]
for n, s in enumerate(plan["shots"]):
    a, b = s["from"], s["from"] + s["dur"]
    ed.append("%03d  AX       V     C        %s %s %s %s" % (n + 1, tc(a), tc(b), tc(a), tc(b)))
    ed.append(f"* FROM CLIP NAME: {NAME}_Picture.mp4 | {label(s)}")
(P / f"{NAME}_cuts.edl").write_text("\n".join(ed) + "\n")

# shot list
with open(P / f"{NAME}_ShotList.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["Shot", "Start TC", "End TC", "Duration s", "Type", "Source file", "Transition", "Narration line"])
    for n, s in enumerate(plan["shots"]):
        a, b = s["from"], s["from"] + s["dur"]
        w.writerow([n + 1, tc(a), tc(b), round(s["dur"] / FPS, 2), label(s), source(s), s.get("trans", "cut"), LINE.get(s["line"], "")])
print("shots", len(vclips), "audio tracks", ti, "xml KB", len(xml) // 1024)
