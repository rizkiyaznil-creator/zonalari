FROM python:3.12-slim

WORKDIR /app

# Sertifikat CA tambahan. Folder ini boleh kosong — dan memang kosong pada
# pemasangan biasa. Diisi hanya bila jaringan memakai proxy pemeriksa TLS.
COPY certs/ /usr/local/share/ca-certificates/extra/
RUN if ls /usr/local/share/ca-certificates/extra/*.crt >/dev/null 2>&1; then \
      update-ca-certificates; \
    fi
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Pembacaan dan perenderan PDF memakai pypdfium2, yang sudah membawa mesin
# PDFium sendiri. Sengaja tidak memakai poppler-utils agar image tidak
# bergantung pada paket sistem — pemasangan di RS jadi lebih sederhana.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
