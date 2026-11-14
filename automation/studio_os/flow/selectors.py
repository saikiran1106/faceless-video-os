"""Google Flow NORMAL-mode controls, verified on the live signed-in UI (September 2026).

Never use Agent mode (house rule): the "Agent" chip in the prompt bar must read aria-pressed="false".
Material ids (mat-button-toggle-N) are generated per page load - select by role + accessible name only.
"""
AGENT_CHIP = ("button", "Agent")                  # aria-pressed must be "false"
AGENT_PANEL_CLOSE = ("button", "Close")           # closes the agent side panel if it opens
SETTINGS_CHIP = ("button", "Settings trigger")    # text like "Video · 720p · 4s | crop_9_16 | x1"
MODE_VIDEO = ("radio", "Video")
VIDEO_FRAMES = ("radio", "Frames")                # first/last-frame mode ("Ingredients" is the other)
ASPECT_9_16 = ("radio", "9:16")
MODEL_MENU = ("button", "Select model family")    # menu items: Omni 1.1 Flash, Veo 3.1 - Lite/Fast/Quality
MODEL_OMNI = ("menuitem", "Omni 1.1 Flash")
RES_720 = ("radio", "720p")
DURATIONS = {4: "4s", 6: "6s", 8: "8s", 10: "10s"}
OUTPUTS_1 = ("radio", "x1")
COST_LINK_TEXT = "credits"                        # <a>"7 credits"</a> inside the settings popover
FRAME_START = ("button", "Start")                 # frame slots appear above the prompt bar in Frames mode
FRAME_END = ("button", "End")
FRAME_SWAP = ("button", "Swap first and last frames")
PROMPT_PLACEHOLDER = "What do you want to create?"
GENERATE = ("button", "Start generation")
ADD_MEDIA = ("button", "Add media menu")
ACCOUNT = ("button", "Account details")           # popover text contains "N Google Flow credits"

# Verified 720p x1 Omni 1.1 Flash prices shown by the UI before generating.
PRICE_720P_X1 = {4: 7, 6: 10, 8: 12, 10: 15}
