import cv2
import mediapipe as mp
import time
import subprocess
import os
import vlc
import threading
import pystray
import pyautogui
import webbrowser
from PIL import Image, ImageDraw
import speech_recognition as sr

# --- Configuration ---
WEBCAM_INDEX = 0
HOLD_SECONDS = 1.5

# Left hand paths
GAME_PATH = r"C:\Program Files\GRYPHLINK\games\EndField Game\Endfield.exe"
MP3_PATH = r"C:\Users\chuon\Downloads\Fun Vscode\EndfieldHandTracker\RIPMG.mp3"
OPERA_PATH = r"C:\Users\chuon\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Opera GX Browser.lnk"

# Right hand paths
SOLIDWORKS_PATH = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\SOLIDWORKS 2025\SOLIDWORKS 2025.lnk"
WEBSITE_URL = "https://chuongtran.netlify.app"
GMAIL_URL = "https://gmail.com"

# Swipe detection settings
SWIPE_THRESHOLD = 0.05
SWIPE_TIME_WINDOW = 0.4
SWIPE_COOLDOWN = 2.0

# 5 finger swipe settings
CLOSE_SWIPE_THRESHOLD = 0.15
CLOSE_SWIPE_TIME_WINDOW = 0.5
CLOSE_SWIPE_COOLDOWN = 2.0

# Scroll settings
SCROLL_AMOUNT = 50
SCROLL_SPEED = 0.02
BOTTOM_THIRD = 0.66

# --- Voice Commands ---
VOICE_COMMANDS = {
    "67": r"C:\Users\chuon\curseforge\minecraft\Install\minecraft.exe",
    # "open chrome": r"C:\Path\To\chrome.exe",
}

# --- MediaPipe Setup ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

FINGER_TIPS = [8, 12, 16, 20]
THUMB_TIP = 4
THUMB_BASE = 2

def count_fingers(hand_landmarks):
    fingers_up = 0
    lm = hand_landmarks.landmark
    if lm[THUMB_TIP].x > lm[THUMB_BASE].x:
        fingers_up += 1
    knuckles = [6, 10, 14, 18]
    for tip, knuckle in zip(FINGER_TIPS, knuckles):
        if lm[tip].y < lm[knuckle].y:
            fingers_up += 1
    return fingers_up

def wait_for_hand_exit(cap, hands, window_name):
    while True:
        s, f = cap.read()
        if not s:
            continue
        f = cv2.flip(f, 1)
        r = hands.process(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        cv2.imshow(window_name, f)
        cv2.waitKey(1)
        if not r.multi_hand_landmarks:
            break

def listen_for_commands(recognizer, microphone, commands):
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        recognizer.energy_threshold = 300
        recognizer.pause_threshold = 1.0
    print("🎤 Voice recognition ready!")
    while True:
        try:
            with microphone as source:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=6)
            phrase = recognizer.recognize_google(audio).lower()
            print(f"🎤 Heard: '{phrase}'")
            for command, path in commands.items():
                if command in phrase:
                    print(f"✅ Matched: '{command}' → launching!")
                    subprocess.Popen(path, shell=True)
                    break
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"❌ Speech error: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")

# --- System Tray ---
def create_tray_icon():
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill=(0, 200, 150))
    return img

def quit_app(icon, item):
    icon.stop()
    os._exit(0)

def run_tray():
    icon = pystray.Icon(
        "HandTracker",
        create_tray_icon(),
        "Endfield Hand Tracker",
        menu=pystray.Menu(
            pystray.MenuItem("Endfield Hand Tracker", None, enabled=False),
            pystray.MenuItem("Quit", quit_app)
        )
    )
    icon.run()

tray_thread = threading.Thread(target=run_tray, daemon=True)
tray_thread.start()

recognizer = sr.Recognizer()
microphone = sr.Microphone(device_index=2)
voice_thread = threading.Thread(
    target=listen_for_commands,
    args=(recognizer, microphone, VOICE_COMMANDS),
    daemon=True
)
voice_thread.start()

# --- Main Loop Setup ---
cap = cv2.VideoCapture(WEBCAM_INDEX, cv2.CAP_DSHOW)
time.sleep(1)

if not cap.isOpened():
    print("❌ Could not open webcam.")
    os._exit(1)

# Left hand state
L_gesture_start_time = None
L_fist_start_time = None
L_close_swipe_start_x = None
L_close_swipe_start_time = None
L_last_close_time = 0
L_last_opera_time = 0
vlc_player = None
last_scroll_time = 0  # ← was missing before!

# Right hand state
R_gesture_start_time = None
R_close_swipe_start_x = None
R_close_swipe_start_time = None
R_last_close_time = 0

while True:
    success, img = cap.read()
    if not success:
        continue

    img = cv2.flip(img, 1)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result = hands.process(img_rgb)

    now = time.time()

    left_count = None
    right_count = None
    left_landmarks = None
    right_landmarks = None

    if result.multi_hand_landmarks and result.multi_handedness:
        for hand_lms, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
            mp_draw.draw_landmarks(img, hand_lms, mp_hands.HAND_CONNECTIONS)
            label = handedness.classification[0].label
            count = count_fingers(hand_lms)
            if label == "Left":
                left_count = count
                left_landmarks = hand_lms
            else:
                right_count = count
                right_landmarks = hand_lms

    # --- Reset timers if hands leave frame ---
    if left_count is None:
        L_gesture_start_time = None
        L_fist_start_time = None
        L_close_swipe_start_x = None
        L_close_swipe_start_time = None
        last_scroll_time = 0

    if right_count is None:
        R_gesture_start_time = None
        R_close_swipe_start_x = None
        R_close_swipe_start_time = None

    # =====================
    # LEFT HAND GESTURES
    # =====================

    # --- LEFT: 5 fingers swipe right → Alt+F4 ---
    if left_count == 5 and left_landmarks is not None:
        wrist_x = left_landmarks.landmark[0].x
        if L_close_swipe_start_x is None:
            L_close_swipe_start_x = wrist_x
            L_close_swipe_start_time = now
        else:
            delta_x = wrist_x - L_close_swipe_start_x
            elapsed = now - L_close_swipe_start_time
            if elapsed <= CLOSE_SWIPE_TIME_WINDOW:
                if delta_x >= CLOSE_SWIPE_THRESHOLD and (now - L_last_close_time) > CLOSE_SWIPE_COOLDOWN:
                    print("❌ Closing active window!")
                    cv2.setWindowProperty("Arknights Endfield Launcher", cv2.WND_PROP_VISIBLE, 0)
                    time.sleep(0.3)
                    pyautogui.hotkey('alt', 'F4')
                    time.sleep(0.3)
                    cv2.setWindowProperty("Arknights Endfield Launcher", cv2.WND_PROP_VISIBLE, 1)
                    L_last_close_time = now
                    L_close_swipe_start_x = None
                    L_close_swipe_start_time = None
            else:
                L_close_swipe_start_x = wrist_x
                L_close_swipe_start_time = now
    else:
        L_close_swipe_start_x = None
        L_close_swipe_start_time = None

    # --- LEFT: 3 fingers top = Launch Arknights, bottom = Scroll Up ---
    if left_count == 3 and left_landmarks is not None:
        index_y = left_landmarks.landmark[8].y
        if index_y > BOTTOM_THIRD:
            L_gesture_start_time = None
            if now - last_scroll_time > SCROLL_SPEED:
                pyautogui.scroll(SCROLL_AMOUNT)
                last_scroll_time = now
            cv2.putText(img, "Scrolling Up...", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 3)
        else:
            if L_gesture_start_time is None:
                L_gesture_start_time = now
            elapsed = now - L_gesture_start_time
            remaining = HOLD_SECONDS - elapsed
            cv2.putText(img, f"L Hold... {remaining:.1f}s", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 3)
            if elapsed >= HOLD_SECONDS:
                print("🚀 Launching Arknights Endfield!")
                subprocess.Popen(GAME_PATH, shell=True)
                L_gesture_start_time = None
                wait_for_hand_exit(cap, hands, "Arknights Endfield Launcher")

    # --- LEFT: 2 fingers bottom = Scroll Down ---
    elif left_count == 2 and left_landmarks is not None:
        index_y = left_landmarks.landmark[8].y
        if index_y > BOTTOM_THIRD:
            if now - last_scroll_time > SCROLL_SPEED:
                pyautogui.scroll(-SCROLL_AMOUNT)
                last_scroll_time = now
            cv2.putText(img, "Scrolling Down...", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 3)
        else:
            last_scroll_time = 0

    # --- LEFT: Fist → Open Opera GX ---
    elif left_count == 0:
        if L_fist_start_time is None:
            L_fist_start_time = now
        elapsed = now - L_fist_start_time
        remaining = HOLD_SECONDS - elapsed
        cv2.putText(img, f"L Hold... {remaining:.1f}s", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 3)
        if elapsed >= HOLD_SECONDS and (now - L_last_opera_time) > 3.0:
            print("🌐 Opening Opera GX!")
            subprocess.Popen(["cmd", "/c", "start", "", OPERA_PATH], shell=True)
            L_last_opera_time = now
            L_fist_start_time = None
            wait_for_hand_exit(cap, hands, "Arknights Endfield Launcher")

    else:
        L_gesture_start_time = None
        L_fist_start_time = None

    # =====================
    # RIGHT HAND GESTURES
    # =====================

    # --- RIGHT: 5 fingers swipe left → Open Gmail ---
    if right_count == 5 and right_landmarks is not None:
        wrist_x = right_landmarks.landmark[0].x
        if R_close_swipe_start_x is None:
            R_close_swipe_start_x = wrist_x
            R_close_swipe_start_time = now
        else:
            delta_x = wrist_x - R_close_swipe_start_x
            elapsed = now - R_close_swipe_start_time
            if elapsed <= CLOSE_SWIPE_TIME_WINDOW:
                if delta_x <= -CLOSE_SWIPE_THRESHOLD and (now - R_last_close_time) > CLOSE_SWIPE_COOLDOWN:
                    print("📧 Opening Gmail!")
                    webbrowser.open(GMAIL_URL)
                    R_last_close_time = now
                    R_close_swipe_start_x = None
                    R_close_swipe_start_time = None
            else:
                R_close_swipe_start_x = wrist_x
                R_close_swipe_start_time = now
    else:
        R_close_swipe_start_x = None
        R_close_swipe_start_time = None

    # --- RIGHT: 3 fingers hold → Launch SolidWorks ---
    if right_count == 3:
        if R_gesture_start_time is None:
            R_gesture_start_time = now
        elapsed = now - R_gesture_start_time
        remaining = HOLD_SECONDS - elapsed
        cv2.putText(img, f"R Hold... {remaining:.1f}s", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 150, 0), 3)
        if elapsed >= HOLD_SECONDS:
            print("🔧 Launching SolidWorks!")
            subprocess.Popen(["cmd", "/c", "start", "", SOLIDWORKS_PATH], shell=True)
            R_gesture_start_time = None
            wait_for_hand_exit(cap, hands, "Arknights Endfield Launcher")

    # --- RIGHT: 2 fingers hold → Open website ---
    elif right_count == 2:
        if R_gesture_start_time is None:
            R_gesture_start_time = now
        elapsed = now - R_gesture_start_time
        remaining = HOLD_SECONDS - elapsed
        cv2.putText(img, f"R Hold... {remaining:.1f}s", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 150, 0), 3)
        if elapsed >= HOLD_SECONDS:
            print("🌍 Opening website!")
            webbrowser.open(WEBSITE_URL)
            R_gesture_start_time = None
            wait_for_hand_exit(cap, hands, "Arknights Endfield Launcher")

    else:
        R_gesture_start_time = None

    # --- HUD Display ---
    cv2.putText(img, f"L: {left_count if left_count is not None else '-'}  R: {right_count if right_count is not None else '-'}",
                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 200), 3)

    cv2.putText(img, "LEFT:", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
    cv2.putText(img, "  3 fingers top = Launch Arknights", (10, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "  3 fingers low = Scroll Up", (10, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "  2 fingers low = Scroll Down", (10, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "  Fist = Open Opera GX", (10, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "  5 fingers swipe right = Close App", (10, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.putText(img, "RIGHT:", (10, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 150, 0), 2)
    cv2.putText(img, "  2 fingers = Open Website", (10, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "  3 fingers = Launch SolidWorks", (10, 295), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(img, "  5 fingers swipe left = Gmail", (10, 315), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.putText(img, "Say 'six seven' = Minecraft", (10, 340),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 100), 1)

    cv2.imshow("Arknights Endfield Launcher", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Cleanup ---
if vlc_player is not None:
    vlc_player.stop()
cap.release()
cv2.destroyAllWindows()
os._exit(0)

# import speech_recognition as sr
# import audioop

# recognizer = sr.Recognizer()
# microphone = sr.Microphone(device_index=3)

# print("🎤 Mic level monitor — speak to see the bar move!")
# print("Press Ctrl+C to stop\n")

# with microphone as source:
#     recognizer.adjust_for_ambient_noise(source, duration=1)
#     print(f"Noise threshold set to: {recognizer.energy_threshold:.0f}\n")

#     while True:
#         try:
#             buffer = source.stream.read(source.CHUNK)
#             rms = audioop.rms(buffer, source.SAMPLE_WIDTH)
#             level = int(rms / 100)
#             bar = "█" * min(level, 50)
#             print(f"\r🎙️  [{bar:<50}] {rms:>6}", end="", flush=True)
#         except KeyboardInterrupt:
#             print("\n\nStopped!")
#             break