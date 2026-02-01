import logging
import os
import subprocess
import time
import platform
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# === CONFIGURATION ===
username = "MagnusCarlsen"
number_of_games = 50
move_delay = 3  # Seconds between moves
stream_to_youtube = True
youtube_stream_url = "rtmp://a.rtmp.youtube.com/live2"
youtube_stream_key = "7v8x-k1dd-r1sb-e1sz-efd2"
output_file = os.path.join(os.getcwd(), "chess_games_recording.mkv")
enable_infinite_loop = True

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)

def start_screen_recording(stream_to_youtube=False, youtube_stream_url="", youtube_stream_key="", output_file="chess_games_recording.mkv"):
    import logging
    import os
    import platform
    import subprocess

    logging.info("[RECORDING] Starting FFmpeg...")

    system_os = platform.system().lower()
    logging.info(f"[SYSTEM] Detected OS: {system_os}")

    # Use parameters from main.py
    if system_os == 'windows':
        input_args = [
            '-f', 'gdigrab',
            '-framerate', '60',
            '-offset_x', '50',
            '-offset_y', '275',
            '-video_size', '1280x720',
            '-i', 'desktop'
        ]
    elif system_os == 'linux':
        display = os.environ.get("DISPLAY", ":99.0")
        input_args = [
            '-f', 'x11grab',
            '-framerate', '60',
            '-video_size', '1280x1024',
            '-draw_mouse', '0',
            '-i', display
        ]
    else:
        raise RuntimeError(f"Unsupported OS: {system_os}")

    music_file = os.path.join(os.getcwd(), 'bgmusic.mp3')
    if os.path.exists(music_file):
        audio_args = ['-stream_loop', '-1', '-i', music_file]
        audio_map = '[2:a]'
    else:
        logging.warning("[AUDIO] Background music not found, using null audio.")
        audio_args = ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']
        audio_map = '[2:a]'

    bottom_video = os.path.join(os.getcwd(), 'bottom-Magnus.mp4')
    banner_args = ['-stream_loop', '-1', '-i', bottom_video]

    Y_SHIFT = -180
    vertical_pad = f"(1280-ih*min(720/iw\\,1280/ih))/2+{Y_SHIFT}"
    
    if system_os == 'windows':
        # Correctly escaped path for FFmpeg filter complex on Windows:  C\:/Windows/Fonts/arialbd.ttf
        # In python string: C\\:/Windows/Fonts/arialbd.ttf
        fontfile_path = "C\\:/Windows/Fonts/arialbd.ttf"
    else:
        fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
 
    filter_args = [
        '-filter_complex',
        f"[0:v]crop=930:900:175:50," 
        f"scale=iw*min(720/iw\\,1280/ih):ih*min(720/iw\\,1280/ih),"
        f"pad=720:1280:(720-iw*min(720/iw\\,1280/ih))/2:{vertical_pad}:black," 
        f"drawtext=fontfile='{fontfile_path}':text='GOAT Chess':"
        f"fontcolor=white:fontsize=48:box=1:boxcolor=black@0.5:boxborderw=10:"
        f"x=(w-text_w)/2:y=60[main];"
        f"[1:v]scale=720:600[banner];"
        f"[main][banner]overlay=0:820[v];"
        f"[2:a]volume=0.1[a]",
        '-map', '[v]',
        '-map', '[a]'
    ]

    encoding_args = [
        '-vcodec', 'libx264',
        '-preset', 'veryfast',
        '-pix_fmt', 'yuv420p',
        '-r', '60',
        '-g', '120',
        '-b:v', '3000k',
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

    command = ['ffmpeg', '-y'] + input_args + banner_args + audio_args + filter_args + encoding_args + output_args
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

def get_game_links(driver):
    url = f"https://www.chess.com/games/archive/{username}?gameType=live"
    logging.info(f"[FETCH] Navigating to: {url}")
    driver.get(url)
    
    # Wait for table
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(3) # Extra wait for rows
        
        # Scrape links
        logging.info("[FETCH] Parsing links...")
        links = []
        # Robust fetch: find all links containing /game/live/
        rows = driver.find_elements(By.XPATH, "//a[contains(@href, '/game/live/')]")
        for r in rows:
            href = r.get_attribute("href")
            if href and href not in links:
                links.append(href)
        
        # Make unique
        links = list(set(links))
        logging.info(f"[FETCH] Found {len(links)} games.")
        return links
    except Exception as e:
        logging.error(f"[FETCH] Error: {e}")
        return []

def close_popups(driver):
    try:
        # Aggressive close strategy for "Join Now" and other modals
        driver.execute_script("""
            // 1. Generic Close buttons
            var close_btns = document.querySelectorAll("button[aria-label='Close'], button[title='Close']");
            close_btns.forEach(b => b.click());
            
            // 2. Icon based close
            var icon_close = document.querySelectorAll(".icon-close, .close-icon");
            icon_close.forEach(i => i.click());
            
            // 3. 'No Thanks' text buttons
            var text_btns = document.querySelectorAll("button");
            text_btns.forEach(b => {
                var t = b.textContent.toLowerCase();
                if(t.includes('no thanks') || t.includes('not now') || t.includes('remind me later')) {
                    b.click();
                }
            });
        """)
        # 4. Escape key fallback
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except: pass

def play_moves(driver):
    logging.info("[PLAY] Starting playback...")
    
    # 1. Close Popups/Modals explicitly at start
    close_popups(driver)
    time.sleep(1)

    # Wait for board
    try:
        # Check for board container
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='board']")))
    except:
        logging.warning("[PLAY] Board not found. Skipping.")
        return

    # Check FEN error
    if "Invalid FEN" in driver.page_source:
        logging.error("[PLAY] Invalid FEN detected! Skipping.")
        return

    # Navigate to start just in case
    try:
        ActionChains(driver).send_keys(Keys.HOME).perform()
        time.sleep(1)
    except: pass
    
    # Play loop
    for i in range(200): # Max moves safeguard
        # Periodic popup check (every 10 moves)
        if i % 10 == 0:
            close_popups(driver)

        # Check for error popup
        if "Invalid FEN" in driver.page_source:
             logging.error("[PLAY] Invalid FEN detected mid-game!")
             break

        # Move forward
        ActionChains(driver).send_keys(Keys.ARROW_RIGHT).perform()
        time.sleep(move_delay)
        
        # Simple stop check: check if Game Result is shown
        if len(driver.find_elements(By.CSS_SELECTOR, "div[class*='game-result']")) > 0:
            logging.info("[PLAY] Game result detected. Stopping.")
            break
        
        # Check for modal
        if len(driver.find_elements(By.CSS_SELECTOR, "div[class*='modal-game-over']")) > 0:
             break

def main():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    # Add anti-detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)
    ffmpeg_proc = None

    try:
        driver.maximize_window() # Force maximize for accurate cropping
        
        while True:
            links = get_game_links(driver)
            if not links:
                logging.error("[MAIN] No games found. Cloudflare might be blocking or invalid user. Retrying in 10s...")
                time.sleep(10)
                continue
            
            # Start Recording on first successful fetch
            if ffmpeg_proc is None:
                logging.info("[RECORDING] Starting FFmpeg...")
                ffmpeg_proc = start_screen_recording(
                    stream_to_youtube=stream_to_youtube,
                    youtube_stream_url=youtube_stream_url,
                    youtube_stream_key=youtube_stream_key,
                    output_file=output_file
                )
                time.sleep(2)

            for i, link in enumerate(links):
                if i >= number_of_games: break
                logging.info(f"[LOOP] Playing game {i+1}: {link}")
                
                try:
                    driver.get(link)
                    play_moves(driver)
                except Exception as e:
                    logging.error(f"[LOOP] Error playing game: {e}")
                
                time.sleep(2)

            if not enable_infinite_loop:
                logging.info("[MAIN] Infinite loop disabled. Exiting.")
                break
                
            logging.info("[MAIN] Restarting list...")
            time.sleep(5)

    except Exception as e:
        logging.error(f"[CRITICAL] {e}")
    finally:
        stop_screen_recording(ffmpeg_proc)
        try: driver.quit()
        except: pass

if __name__ == "__main__":
    main()
