import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# Setup simplified logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

def test_selectors():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # Headless for speed/compatibility in this environment
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        logging.info("Navigating to https://chesskit.org/ ...")
        driver.get("https://chesskit.org/")
        
        # 1. Load a game to get to the board
        logging.info("Clicking 'Load game'...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Load game')]"))).click()
        
        # Select Chess.com if needed (default usually works if it shows lists)
        logging.info("Waiting for game list...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[@data-sentry-component='GameItem'] | //*[contains(text(), 'vs')]")))
        
        games = driver.find_elements(By.XPATH, "//li[@data-sentry-component='GameItem']")
        if not games:
            logging.info("No explicit GameItems found, looking for fallbacks...")
            games = driver.find_elements(By.XPATH, "//div[contains(@class, 'MuiListItem-root')] | //li[contains(@class, 'MuiListItem-root')]")
            
        if games:
            logging.info(f"Found {len(games)} games. Clicking the first one...")
            driver.execute_script("arguments[0].click();", games[0])
            time.sleep(3) # Wait for board load
        else:
            logging.error("Could not find any games to click.")
            return

        # 2. Inspect the Control Bar
        logging.info("--- INSPECTING CONTROL BUTTONS ---")
        
        # Dump all buttons in the likely control area (usually bottom of board)
        buttons = driver.find_elements(By.TAG_NAME, "button")
        logging.info(f"Found {len(buttons)} total buttons on page. Filtering for interesting ones...")
        
        candidates = []
        for btn in buttons:
            try:
                html = btn.get_attribute("outerHTML")
                label = btn.get_attribute("aria-label")
                title = btn.get_attribute("title")
                text = btn.text
                
                # Check if it looks relevant
                is_relevant = False
                if label and "move" in label.lower(): is_relevant = True
                if title and "move" in title.lower(): is_relevant = True
                if "reset" in (label or "").lower() or "reset" in (title or "").lower(): is_relevant = True
                if "arrow" in html: is_relevant = True
                if "Analyze" in html: is_relevant = True
                
                if is_relevant:
                    candidates.append({
                        "text": text,
                        "label": label,
                        "title": title,
                        "html_snippet": html[:200]
                    })
            except:
                continue
                
        for i, c in enumerate(candidates):
            logging.info(f"Candidate {i}: Text='{c['text']}' Label='{c['label']}' Title='{c['title']}' HTML={c['html_snippet']}")

    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_selectors()
