import logging
import os
import subprocess
import time
import platform
import tempfile
import sys
import requests
import datetime
import re


from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException

# ================= CONFIG =================
username = "MagnusCarlsen"
# API specific config
target_year = "2026"
target_month = "01"

move_delay = 3
stream_to_youtube = True

output_file = os.path.join(os.getcwd(), "chess_games_recording.mkv")
youtube_stream_url = "rtmp://a.rtmp.youtube.com/live2"
youtube_stream_key = "7v8x-k1dd-r1sb-e1sz-efd2"

enable_infinite_loop = True

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)

# ================= SAFETY =================
def ensure_browser_alive(driver):
    try:
        _ = driver.title
    except WebDriverException:
        logging.error("[FATAL] Browser session lost. Exiting.")
        sys.exit(1)

# ================= PGN FORMATTING =================
def format_pgn_to_standard(raw_pgn):
    if not raw_pgn:

        return ""
        
    lines = raw_pgn.split('\n')
    headers = []
    movement_lines = []
    
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('['):
            # Keep all headers that match the [Key "Value"] format
            if re.match(r'\[\w+ ".*"\]', line):
                headers.append(line)
        else:
            movement_lines.append(line)
    
    # Process move text
    move_text = " ".join(movement_lines)
    
    # Remove comments { ... }
    move_text = re.sub(r'\{.*?\}', '', move_text, flags=re.DOTALL)
    # Remove annotations like $1, $2
    move_text = re.sub(r'\$\d+', '', move_text)
    # Remove redundant "1..." / "1. ..." notations
    move_text = re.sub(r'\d+\s*\.\.\.', '', move_text)
    
    # Standardize spacing
    move_text = re.sub(r'\s+', ' ', move_text).strip()
    
    # Final reconstruction: Headers -> Empty Line -> Moves
    return "\n".join(headers) + "\n\n" + move_text

# ================= API FETCH =================
def fetch_pgns(username, year, month):
    url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month}"
    logging.info(f"[API] Fetching games from {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        games = data.get("games", [])
        
        valid_pgns = []
        for g in games:
            # Filter for standard chess
            if g.get("rules") == "chess" and g.get("pgn"):
                # Convert to accepted format immediately
                formatted = format_pgn_to_standard(g.get("pgn"))
                if formatted:
                    valid_pgns.append(formatted)
        
        logging.info(f"[API] Found and formatted {len(valid_pgns)} valid games")
        return valid_pgns
    except Exception as e:
        logging.error(f"[API] Failed to fetch games: {e}")
        return []

# ================= FFMPEG =================
def start_screen_recording(stream_to_youtube=False, youtube_stream_url="", youtube_stream_key="", output_file="chess_games_recording.mkv"):
    logging.info("[RECORDING] Starting FFmpeg...")

    system_os = platform.system().lower()
    logging.info(f"[SYSTEM] Detected OS: {system_os}")

    if system_os == 'windows':
        input_args = [
            '-f', 'gdigrab',
            '-framerate', '60',
            '-offset_x', '25',
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

    # Background music setup
    music_file = os.path.join(os.getcwd(), 'bgmusic.mp3')
    if os.path.exists(music_file):
        audio_args = ['-stream_loop', '-1', '-i', music_file]
    else:
        logging.warning("[AUDIO] Background music not found, using null audio.")
        audio_args = ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']

    # Bottom Magnus video setup
    bottom_video = os.path.join(os.getcwd(), 'bottom-Magnus.mp4')
    if os.path.exists(bottom_video):
        banner_args = ['-stream_loop', '-1', '-i', bottom_video]
    else:
        logging.warning("[VIDEO] bottom-Magnus.mp4 not found, falling back.")
        # We need a dummy input if missing to keep mapping consistent, or skip mapping
        banner_args = ['-f', 'lavfi', '-i', 'color=c=black:s=720x600:d=1']

    # === ADJUSTABLE STREAM PARAMETERS ===
    # Increase CROP_Y to skip the top website header (chesskit menu)
    CROP_Y = 210  
    # Decrease CROP_W to cut off the right-side analysis panel
    CROP_W = 580  
    # Adjust CROP_H to tightly fit names and the board (remove bottom grey area)
    CROP_H = 650  
    # Small CROP_X ensures the evaluation bar on the left is included
    CROP_X = 20   
    # Use Y_SHIFT to move the entire content block up or down in the 1280p frame
    Y_SHIFT = -100 
    # Magnus banner height
    BANNER_H = 450
    # Magnus banner vertical position (increase to move toward bottom)
    BANNER_Y = 975

    # Pre-calculate the vertical padding formula
    vertical_pad = f"(1280-ih*min(720/iw\\,1280/ih))/2+{Y_SHIFT}"
    
    if system_os == 'windows':
        fontfile_path = "C\\:/Windows/Fonts/arialbd.ttf"
    else:
        fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    filter_args = [
        '-filter_complex',
        # 1. Crop the board + evaluation bar + names
        f"[0:v]crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y},"
        # 2. Scale to fit stream width (720px)
        f"scale=720:-1[board];"
        # 3. Create the vertical background and place the header text
        f"[board]pad=720:1280:(720-iw)/2:{vertical_pad}:black,"
        f"drawtext=fontfile='{fontfile_path}':text='GOAT Chess':"
        f"fontcolor=white:fontsize=48:box=1:boxcolor=black@0.5:boxborderw=10:"
        f"x=(w-text_w)/2:y=30[main];"
        # 4. Process the bottom banner
        f"[1:v]scale=720:{BANNER_H}[banner];"
        # 5. Overlay banner.
        f"[main][banner]overlay=0:{BANNER_Y}[v];"
        "[2:a]volume=0.2[a]",
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

def stop_screen_recording(proc):
    if proc:
        try:
            proc.communicate(input=b"q", timeout=5)
        except:
            proc.terminate()

# ================= GAME PLAY =================
def play_all_moves(driver, wait, game_info="Unknown Game"):

    ensure_browser_alive(driver)

    logging.info("[PLAY] Waiting for game navigation controls...")
    
    # SVG path provided by user for the "Next Move" icon
    next_move_xpath = "//*[local-name()='path' and @d='m13.172 12l-4.95-4.95l1.414-1.413L16 12l-6.364 6.364l-1.414-1.415z']/ancestor::*[local-name()='button' or @role='button']"
    
    try:
        # Wait until the next move button is present
        wait.until(EC.presence_of_element_located((By.XPATH, next_move_xpath)))
        logging.info("[PLAY] Next move button found.")
    except:
        logging.warning("[PLAY] Next move button not found. Game might not have loaded or controls are hidden.")
        return

    # Play moves
    move_count = 0
    
    while True:
        ensure_browser_alive(driver)
        
        try:
            # Re-locate button each time to avoid stale reference
            btn = driver.find_element(By.XPATH, next_move_xpath)
            
            # Check if disabled
            if btn.get_attribute("disabled"):
                logging.info(f"[PLAY] End of game reached after {move_count} moves.")
                break
            
            btn.click()
            move_count += 1
            logging.info(f"[PLAY] [{game_info}] Playing move {move_count}...")

            
            time.sleep(move_delay)
            
        except Exception as e:
            logging.info(f"[PLAY] Navigation stopped: {e}")
            break

# ================= LOAD GAME VIA PGN =================
def load_game_via_pgn(driver, wait, pgn_text):
    ensure_browser_alive(driver)
    
    logging.info("[LOAD] Opening Load Game dialog...")
    try:
        # Try finding "Load another game" first (end of game state)
        try:
            load_another_btn = driver.find_element(By.XPATH, "//p[contains(text(), 'Load another game')]")
            driver.execute_script("arguments[0].click();", load_another_btn)
            logging.info("[LOAD] Clicked 'Load another game'")
        except:
            # Fallback to standard "Load game" button (initial state)
            load_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Load game')]")
            ))
            driver.execute_script("arguments[0].click();", load_btn)

        # Dropdown trigger
        dropdown_trigger = wait.until(EC.element_to_be_clickable((By.ID, "dialog-select")))
        dropdown_trigger.click()
        
        # Click "PGN"
        pgn_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//li[contains(text(), 'PGN') or contains(text(), 'pgn')]")
        ))
        pgn_option.click()
        
        # Locate the specific visible textarea
        textarea_xpath = "//textarea[not(@aria-hidden='true')]"
        textarea = wait.until(EC.visibility_of_element_located((By.XPATH, textarea_xpath)))
        
        # Inject PGN using framework-safe method
        logging.info("[LOAD] Entering PGN...")
        driver.execute_script("""
            const textarea = arguments[0];
            const value = arguments[1];
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeInputValueSetter.call(textarea, value);
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
            textarea.dispatchEvent(new Event('blur', { bubbles: true }));
        """, textarea, pgn_text)
        
        time.sleep(1)
        
        # Trigger validation
        try:
            textarea.click()
            time.sleep(0.5)
            textarea.send_keys(Keys.END)
            textarea.send_keys(" ")
            textarea.send_keys(Keys.BACKSPACE)
        except:
            pass

        # Wait as requested
        time.sleep(2)
        
        # Final Verification
        final_val = textarea.get_attribute("value")
        if not final_val or len(final_val) < 10:
             driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
             """, textarea, pgn_text)
             time.sleep(1)

        # Click "Add" 
        try:
            dialog = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[@role='dialog']")))
            submit_btn_xpath = ".//button[contains(@class, 'MuiButton-containedPrimary') and text()='Add']"
            
            submit_btn = None
            for attempt in range(6):
                try:
                    submit_btn = dialog.find_element(By.XPATH, submit_btn_xpath)
                    if submit_btn and submit_btn.is_enabled():
                        break
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", textarea)
                except:
                    pass
                time.sleep(1)

            if submit_btn and submit_btn.is_enabled():
                logging.info("[LOAD] Clicking Add...")
                try:
                    submit_btn.click()
                except:
                    driver.execute_script("arguments[0].click();", submit_btn)
                time.sleep(1)
            else:
                logging.warning("[LOAD] Add button not clickable.")
        
        except Exception as e:
            logging.error(f"[LOAD] Dialog error: {e}")

        # Wait for closure
        for i in range(15):
            try:
                open_dialogs = driver.find_elements(By.XPATH, "//div[@role='dialog']")
                if not open_dialogs or not open_dialogs[0].is_displayed():
                    return True
                
                err_nodes = driver.find_elements(By.XPATH, "//*[contains(text(), 'Invalid') or contains(text(), 'error') or contains(text(), 'failed')]")
                for node in err_nodes:
                    if node.is_displayed() and node.text.strip():
                        logging.error(f"[LOAD] Site error: {node.text}")
                
                time.sleep(1)
            except:
                return True
        
        return False

    except Exception as e:
        logging.error(f"[LOAD] Exception: {e}")
        try:
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except:
            pass
        return False

# ================= MAIN =================
def main():
    ffmpeg_proc = None

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")

    if platform.system() == "Linux":
        if not os.environ.get("DISPLAY"):
            os.environ["DISPLAY"] = ":99"
        profile = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Fixed window size for consistent capture in Docker
        options.add_argument("--window-size=1280,1024")
        options.add_argument("--force-device-scale-factor=1")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        logging.info("Navigating to chesskit.org...")
        driver.get("https://chesskit.org/")
        
        # Initial wait
        time.sleep(5) 
        
        all_pgns = fetch_pgns(username, target_year, target_month)
        if not all_pgns:
            logging.error("No games found from API.")
            return

        game_idx = 0
        while True:
            if game_idx >= len(all_pgns):
                if enable_infinite_loop:
                    game_idx = 0
                    logging.info("Looping back to first game.")
                else:
                    logging.info("All games played.")
                    break
            
            pgn = all_pgns[game_idx]
            
            # Extract game info for better logging
            white = re.search(r'\[White "(.*?)"\]', pgn)
            black = re.search(r'\[Black "(.*?)"\]', pgn)
            white_name = white.group(1) if white else "White"
            black_name = black.group(1) if black else "Black"
            game_info = f"{white_name} vs {black_name} ({game_idx+1}/{len(all_pgns)})"
            
            logging.info(f"playing game {game_info}")

            
            success = load_game_via_pgn(driver, wait, pgn)
            
            if success:
                 if ffmpeg_proc is None:
                    ffmpeg_proc = start_screen_recording(
                        stream_to_youtube,
                        youtube_stream_url,
                        youtube_stream_key,
                        output_file
                    )
                 play_all_moves(driver, wait, game_info)
            else:
                 logging.warning(f"Skipping game {game_idx+1} due to load failure.")
            
            game_idx += 1
            # Small buffer between games
            time.sleep(1)

    finally:
        stop_screen_recording(ffmpeg_proc)
        driver.quit()

if __name__ == "__main__":
    main()
