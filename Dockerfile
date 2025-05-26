FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y     libcairo2     libpango-1.0-0     fonts-dejavu     fontconfig     && rm -rf /var/lib/apt/lists/*

# Copiar fuentes Poppins al sistema
RUN mkdir -p /usr/share/fonts/truetype/poppins
COPY templates/fonts /usr/share/fonts/truetype/poppins
RUN fc-cache -f -v

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "main:app"]