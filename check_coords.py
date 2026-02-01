from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

def get_board_coords():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--force-device-scale-factor=1")
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://chesskit.org/")
        time.sleep(5)
        # Check if the board is present
        board = driver.find_element(By.CSS_SELECTOR, "div[class*='board']")
        loc = board.location
        size = board.size
        print(f"Board Location: {loc}")
        print(f"Board Size: {size}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    get_board_coords()
