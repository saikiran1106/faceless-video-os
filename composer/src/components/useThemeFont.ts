import { useEffect, useState } from "react";
import { continueRender, delayRender, staticFile } from "remotion";
import { Theme } from "../types";

// A channel can ship its own font file (needed for scripts like Telugu,
// Devanagari or Arabic that system fonts render poorly). The render waits
// until it has loaded so no frame is drawn in a fallback face.
export function useThemeFont(theme: Theme): string {
  const fallback = `${theme.fontFamily}, "Noto Sans", Inter, "Helvetica Neue", Arial, sans-serif`;
  const [handle] = useState(() => (theme.fontSrc ? delayRender(`font ${theme.fontSrc}`) : null));
  useEffect(() => {
    if (!theme.fontSrc || handle === null) return;
    const face = new FontFace("FacelessCustom", `url(${staticFile(theme.fontSrc)})`);
    face
      .load()
      .then((loaded) => {
        document.fonts.add(loaded);
        continueRender(handle);
      })
      .catch((err) => {
        console.error("Font failed to load, using fallback", err);
        continueRender(handle);
      });
  }, [theme.fontSrc, handle]);
  return theme.fontSrc ? `"FacelessCustom", ${fallback}` : fallback;
}
