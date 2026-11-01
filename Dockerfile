FROM python:3.12-slim
WORKDIR /app
# ffmpeg merges Instagram's separate video and audio; gcc only builds tgcrypto, then goes
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg gcc libc6-dev \
 && pip install --no-cache-dir tgcrypto tzdata \
 && apt-get purge -y gcc libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
ENV DATA_DIR=/data PYTHONUNBUFFERED=1 DAILY_RESTART=1
# TikTok and Instagram change often, so get the newest downloaders on every start
CMD ["sh", "-c", "pip install -q --no-cache-dir --root-user-action=ignore --disable-pip-version-check -U yt-dlp gallery-dl; exec python bot.py"]
