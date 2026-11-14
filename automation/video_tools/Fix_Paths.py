"""Optional helper. Run ONLY if Premiere shows the media as offline after importing <NAME>_Premiere.xml.
It writes <NAME>_Premiere_ABSOLUTE.xml with full paths for wherever this folder is on your computer, then import THAT file.
Usage:  python Fix_Paths.py     (Python 3, no extra packages)"""
import os, re, sys, urllib.parse
here = os.path.dirname(os.path.abspath(__file__))
import glob
src = [f for f in sorted(glob.glob(os.path.join(here, "*_Premiere.xml")))][0]; dst = src.replace("_Premiere.xml", "_Premiere_ABSOLUTE.xml")
def url(rel):
    p = os.path.join(here, *rel.split("/")).replace("\\", "/")
    if re.match(r"^[A-Za-z]:", p): p = "/" + p[0] + ":" + p[2:]          # Windows drive letter
    return "file://localhost" + urllib.parse.quote(p, safe="/:")
xml = open(src, encoding="utf-8").read()
xml = re.sub(r"<pathurl>(Media/[^<]+)</pathurl>", lambda m: "<pathurl>" + url(m.group(1)) + "</pathurl>", xml)
open(dst, "w", encoding="utf-8").write(xml); print("wrote", dst)
