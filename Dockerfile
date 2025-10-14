# Gunakan image resmi Playwright (sudah include Chromium + deps)
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# (base image sudah punya browser, ini untuk jaga-jaga)
RUN playwright install --with-deps chromium

COPY . .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000

# Jalankan API (Gunicorn + Uvicorn worker)
CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","-w","2","-b","0.0.0.0:8000","backend.app:app"]