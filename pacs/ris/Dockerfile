FROM python:3.12-slim

WORKDIR /app

# Sertifikat CA tambahan. Folder ini boleh kosong — dan memang kosong pada
# pemasangan biasa. Diisi hanya bila jaringan RS memakai proxy yang memeriksa
# TLS, sehingga pip tidak bisa mengunduh paket tanpa CA milik proxy tersebut.
COPY certs/ /usr/local/share/ca-certificates/extra/
RUN if ls /usr/local/share/ca-certificates/extra/*.crt >/dev/null 2>&1; then \
      update-ca-certificates; \
    fi
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
