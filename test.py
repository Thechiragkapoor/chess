import logging
import os
import subprocess
import time
import platform
import tempfile
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# === CONFIGURATION ===
username = "MagnusCarlsen"
number_of_games = 50
move_delay = 2  # seconds
stream_to_youtube = True  # ✅ Set to True to stream, False to record locally
output_file = os.path.join(os.getcwd(), "chess_games_recording.mkv")
youtube_stream_url = "rtmp://a.rtmp.youtube.com/live2"
youtube_stream_key = "7v8x-k1dd-r1sb-e1sz-efd2"
username_entered = False  # Track if username has already been entered
enable_infinite_loop = True  # Set to False to run only once

# === LOGGING SETUP ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)


def start_screen_recording(stream_to_youtube=False, youtube_stream_url="", youtube_stream_key="", output_file="chess_games_recording.mkv"):
    import logging
    import os
    import platform
    import subprocess

    logging.info("[RECORDING] Starting FFmpeg...")

    system_os = platform.system().lower()
    logging.info(f"[SYSTEM] Detected OS: {system_os}")

    if system_os == 'windows':
        input_args = [
            '-f', 'gdigrab',
            '-framerate', '60',
            '-offset_x', '25',
            '-offset_y', '275',
            '-video_size', '1280x720',  # Full screen capture, crop will trim
            '-i', 'desktop'
        ]
    elif system_os == 'linux':
        display = os.environ.get("DISPLAY", ":99.0")
        input_args = [
            '-f', 'x11grab',
            '-framerate', '60',
            '-video_size', '1280x1024',
            '-draw_mouse', '0',       # 👈 disables the mouse pointer
            '-i', display
        ]
    else:
        raise RuntimeError(f"Unsupported OS: {system_os}")

    # Background music setup
    music_file = os.path.join(os.getcwd(), 'bgmusic.mp3')
    if os.path.exists(music_file):
        audio_args = ['-stream_loop', '-1', '-i', music_file]
        audio_map = '[1:a]'
    else:
        logging.warning("[AUDIO] Background music not found, using null audio.")
        audio_args = ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']
        audio_map = '[1:a]'

    # Crop the screen area, then scale to 1280x720 (letterboxing or padding can be added if needed)
    filter_args = [
        '-filter_complex',
        f"[0:v]crop=640:620:210:245,scale=iw*min(720/iw\\,1280/ih):ih*min(720/iw\\,1280/ih),pad=720:1280:(720-iw*min(720/iw\\,1280/ih))/2:(1280-ih*min(720/iw\\,1280/ih))/2[v];[1:a]anull[a]",
        '-map', '[v]',
        '-map', '[a]'
    ]

    encoding_args = [
    '-vcodec', 'libx264',
    '-preset', 'veryfast',
    '-pix_fmt', 'yuv420p',
    '-r', '60',                          # 60fps
    '-g', '120',                         # keyframe every 2 sec
    '-b:v', '3000k',                     # target 3Mbps for YouTube 720p
    '-minrate', '3000k',
    '-maxrate', '3000k',
    '-bufsize', '6000k',
    '-x264-params', 'nal-hrd=cbr:force-cfr=1',
    '-acodec', 'aac',
    '-ar', '44100',
    '-b:a', '160k',
    '-threads', '4',
    '-shortest'
]

    output_args = ['-f', 'flv', f"{youtube_stream_url}/{youtube_stream_key}"] if stream_to_youtube else [output_file]

    command = ['ffmpeg', '-y'] + input_args + audio_args + filter_args + encoding_args + output_args
    logging.info(f"[FFMPEG COMMAND] {' '.join(command)}")

    return subprocess.Popen(command, stdin=subprocess.PIPE)




def stop_screen_recording(ffmpeg_proc):
    if ffmpeg_proc:
        try:
            ffmpeg_proc.communicate(input='q'.encode(), timeout=5)
            logging.info("[RECORDING] FFmpeg stopped gracefully.")
        except subprocess.TimeoutExpired:
            ffmpeg_proc.terminate()
            logging.warning("[RECORDING] FFmpeg forcibly terminated.")


def play_all_moves(driver, wait, game_index):
    move_count = 0
    fallback_counter = 0
    max_fallback_attempts = 6

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Go to next move']//button")))
    except:
        logging.warning("[MOVE] First move button not found. Game might not be loaded.")
        return

    while True:
        try:
            next_button_wrapper = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Go to next move']")))
            next_button = next_button_wrapper.find_element(By.TAG_NAME, "button")

            if not next_button.is_enabled():
                fallback_counter += 1
                logging.info(f"[MOVE] Next button disabled, attempt {fallback_counter}")
                if fallback_counter >= max_fallback_attempts:
                    logging.info("[MOVE] All moves played.")
                    break
                time.sleep(0.5)
                continue

            driver.execute_script("arguments[0].click();", next_button)
            move_count += 1
            logging.info(f"[GAME] {game_index+1} [MOVE] Played move {move_count}")
            fallback_counter = 0
            time.sleep(move_delay)

        except Exception as e:
            logging.warning(f"[MOVE] Exception during move playback: {e}")
            break


def load_game(driver, wait, game_index):
    global username_entered
    logging.info(f"[LOAD] Loading game {game_index + 1}...")

    if username_entered:
        try:
            load_another = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Load another game')]")))
            load_another.click()
        except Exception as e:
            logging.warning(f"[LOAD] Could not click 'Load another game': {e}")

    try:
        wait.until(EC.element_to_be_clickable((By.ID, "dialog-select"))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(), 'Chess.com')]"))).click()
    except Exception as e:
        logging.error(f"[LOAD] Error opening source dialog: {e}")
        return False

    if not username_entered:
        try:
            username_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
            username_input.clear()
            username_input.send_keys(username)
            time.sleep(2)
            username_entered = True
        except Exception as e:
            logging.warning(f"[LOAD] Could not input username: {e}")

    game_xpath = f"(//div[contains(@class, 'MuiListItemButton-root')])[{game_index + 1}]"
    try:
        game_item = wait.until(EC.element_to_be_clickable((By.XPATH, game_xpath)))
        game_item.click()
    except:
        logging.error(f"[LOAD] Game {game_index + 1} not found.")
        return False

    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add')]"))).click()
        time.sleep(3)
    except Exception as e:
        logging.error(f"[LOAD] Could not click 'Add' button: {e}")
        return False

    return True


def main():
    ffmpeg_proc = None
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--start-maximized")

    if platform.system() == "Linux":
        logging.info("[SYSTEM] Detected Linux OS")

        if not os.environ.get("DISPLAY"):
            logging.info("[XVFB] Setting DISPLAY=:99")
            os.environ["DISPLAY"] = ":99"

        profile_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)

    try:
        logging.info("[BROWSER] Navigating to site...")
        driver.get("https://freechess.web.app/")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Load game')]"))).click()

        while True:
            for i in range(number_of_games):
                logging.info(f"[LOOP] Playing game {i+1}...")

                success = load_game(driver, wait, i)
                if not success:
                    logging.error(f"[LOAD] Failed to load game {i+1}. Exiting inner loop.")
                    break

                if i == 0 and ffmpeg_proc is None:
                    logging.info("[RECORDING] Starting after first game load.")
                    ffmpeg_proc = start_screen_recording(
    stream_to_youtube=stream_to_youtube,
    youtube_stream_url=youtube_stream_url,
    youtube_stream_key=youtube_stream_key,
    output_file=output_file
)
                    time.sleep(1)

                play_all_moves(driver, wait, i)

            if not enable_infinite_loop:
                logging.info("[LOOP] Infinite loop disabled. Exiting after one iteration.")
                break

            logging.info("[LOOP] Completed all games. Restarting loop...")
            time.sleep(2)

    except Exception as e:
        logging.error(f"[ERROR] {e}")
    finally:
        logging.info("[CLEANUP] Finalizing...")
        stop_screen_recording(ffmpeg_proc)
        driver.quit()
        logging.info(f"[SAVED] Video saved to: {output_file}")


if __name__ == "__main__":
    main()
