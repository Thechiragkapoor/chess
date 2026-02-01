FROM python:3.10-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg ca-certificates \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
    libxdamage1 libxrandr2 xdg-utils libu2f-udev libvulkan1 libxss1 \
    libappindicator3-1 libgbm1 libxshmfence1 xvfb jq ffmpeg fonts-dejavu-core \
    && apt-get clean

# Install Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# Dynamically fetch matching ChromeDriver
RUN CHROME_MAJOR=$(google-chrome --version | grep -oP '\d+' | head -n1) && \
    echo "Detected Chrome Major Version: $CHROME_MAJOR" && \
    DRIVER_VERSION=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json \
    | jq -r --arg milestone "$CHROME_MAJOR" '.milestones[$milestone].downloads.chromedriver[] | select(.platform == "linux64") | .url') && \
    echo "Fetching driver from $DRIVER_VERSION" && \
    curl -sSL "$DRIVER_VERSION" -o chromedriver.zip && \
    unzip chromedriver.zip && mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && rm -rf chromedriver.zip chromedriver-linux64

# Set display
ENV DISPLAY=:99

# Install Python dependencies directly
RUN pip install selenium requests

# Copy app
COPY . /app

# Start virtual display and run the Python script
CMD ["bash", "-c", "rm -f /tmp/.X99-lock && Xvfb :99 -ac -screen 0 1280x1024x24 & exec python main.py"]
