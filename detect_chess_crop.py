import os
import subprocess
import cv2

# Path to output screenshot
screenshot_path = "full_screen.png"

# Take a screenshot using FFmpeg from Xvfb display :99
def capture_full_screen():
    print("[INFO] Capturing full screen from :99...")
    subprocess.run([
        "ffmpeg",
        "-y",
        "-f", "x11grab",
        "-video_size", "1280x1024",  # adjust to your virtual screen size
        "-i", ":99.0+0,0",
        "-frames:v", "1",
        screenshot_path
    ])

# Let user select a rectangle (crop) and print coordinates
def select_crop_coordinates():
    print("[INFO] OpenCV: Select the chessboard region and press ENTER or SPACE.")
    img = cv2.imread(screenshot_path)
    if img is None:
        print("[ERROR] Screenshot not found!")
        return

    r = cv2.selectROI("Select Chessboard", img, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = r
    print(f"\n✅ Crop coordinates found:")
    print(f"    crop={w}:{h}:{x}:{y}")
    print(f"\nUse in FFmpeg filter like:")
    print(f"    crop={w}:{h}:{x}:{y}")

if __name__ == "__main__":
    capture_full_screen()
    select_crop_coordinates()
