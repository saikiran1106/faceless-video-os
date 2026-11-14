#!/usr/bin/env python3
"""Upload a campaign's exports to R2 and print 7-day download links.

  python3 tools/deliver.py campaigns/<id> [--hero <variant>] [--extra thumb.png caption.txt]

Uploads every export in exports/delivery_manifest.json plus one zip of all of them, under
motion-studio/<campaign>/ in the bucket, and checks each object's size after upload. Links force a download
(Content-Disposition: attachment) so they work from a phone. Credentials come from the repo .env through
tools/storage/r2.py and are never printed. The links file (exports/r2_links.json) is gitignored: the URLs
carry the access key id.
"""
import argparse
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "tools", "storage"))
import r2  # noqa: E402

WEEK = 604800


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_dir")
    ap.add_argument("--hero", help="variant to link on its own")
    ap.add_argument("--extra", nargs="*", default=[], help="other files to upload (thumbnail, caption)")
    a = ap.parse_args()
    cdir = os.path.abspath(a.campaign_dir)
    man = json.load(open(os.path.join(cdir, "exports", "delivery_manifest.json")))
    bad = [x["id"] for x in man["exports"] if x.get("qa") != "pass"]
    if bad:
        print("warning: QA did not pass for", ", ".join(bad), "- read their qa/<variant>/REVIEW.md before sending")
    prefix = f"motion-studio/{man['campaign']}/"

    zpath = os.path.join(cdir, "exports", f"{man['campaign']}_all_{len(man['exports'])}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for x in man["exports"]:
            z.write(os.path.join(ROOT, x["file"]), os.path.basename(x["file"]))
        z.write(os.path.join(cdir, "exports", "delivery_manifest.json"), "delivery_manifest.json")

    files = [os.path.join(ROOT, x["file"]) for x in man["exports"]] + [zpath] + [os.path.abspath(p) for p in a.extra]
    links = {}
    for p in files:
        name = os.path.basename(p)
        key = prefix + name
        res = r2.put_file(p, key)
        head = r2.client().head_object(Bucket=r2.bucket(), Key=key)
        assert head["ContentLength"] == res["bytes"] == os.path.getsize(p), f"size mismatch for {key}"
        links[name] = r2.presign_get(key, ttl=WEEK, download_name=name)
    out = os.path.join(cdir, "exports", "r2_links.json")
    json.dump(dict(prefix=prefix, expires_in_s=WEEK, links=links), open(out, "w"), indent=1)
    show = [os.path.basename(zpath)] + ([a.hero + ".mp4"] if a.hero else []) + [os.path.basename(p) for p in a.extra]
    for n in show:
        print(f"{n}\n{links[n]}\n")
    print(f"all {len(links)} links in {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
