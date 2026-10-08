"""Одноразовая начальная настройка стенда (запускается сервисом `bootstrap`).

Делает ровно две вещи, которые Terraform сам для себя сделать не может
("яйцо и курица": чтобы Terraform заработал, ему уже нужны хранилище и токен):

  1. Создаёт в MinIO бакет для Terraform state (и включает версионирование,
     чтобы можно было откатить state).
  2. Создаёт в Grafana service account "terraform" и выпускает ему токен.

Результат — файл /out/terraform.env (на вашем компьютере: ./.secrets/terraform.env).
Это набор строк КЛЮЧ=ЗНАЧЕНИЕ с адресами и секретами для Terraform.

Скрипт можно запускать сколько угодно раз: старые токены удаляются, выдаётся новый.
"""
import datetime
import hashlib
import hmac
import os
import sys
import time
import urllib.parse
import base64

from common import http, log, wait_until

GRAFANA = os.environ["GRAFANA_INTERNAL_URL"].rstrip("/")
GF_USER = os.environ["GRAFANA_ADMIN_USER"]
GF_PASS = os.environ["GRAFANA_ADMIN_PASSWORD"]
MINIO = os.environ["MINIO_INTERNAL_URL"].rstrip("/")
S3_USER = os.environ["MINIO_ROOT_USER"]
S3_PASS = os.environ["MINIO_ROOT_PASSWORD"]
BUCKET = os.environ["TF_STATE_BUCKET"]
OUT_DIR = os.environ.get("OUT_DIR", "/out")
REGION = "us-east-1"
SA_NAME = "terraform"
TOKEN_NAME = "terraform-token"

ADMIN_AUTH = "Basic " + base64.b64encode(f"{GF_USER}:{GF_PASS}".encode()).decode()


# ----------------------------------------------------------------- S3 (MinIO)
def _sign(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def s3_request(method, path, query="", body=b""):
    """Запрос к S3 API с подписью AWS Signature V4 (как это делает aws-cli).
    Своей реализацией, чтобы не тащить в образ aws-cli/boto3."""
    host = urllib.parse.urlparse(MINIO).netloc
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join([method, path, query, canonical_headers, signed_headers, payload_hash])
    scope = f"{date}/{REGION}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(("AWS4" + S3_PASS).encode(), date)
    for part in (REGION, "s3", "aws4_request"):
        k = _sign(k, part)
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (f"AWS4-HMAC-SHA256 Credential={S3_USER}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")
    url = MINIO + path + (("?" + query) if query else "")
    return http("PUT" if method == "PUT" else method, url, body or None, raw=True,
                headers={"x-amz-date": amz_date, "x-amz-content-sha256": payload_hash,
                         "Authorization": auth})


def ensure_bucket():
    status, payload = s3_request("PUT", f"/{BUCKET}")
    if status == 200:
        log(f"✅ MinIO: бакет '{BUCKET}' создан")
    elif status == 409 and b"BucketAlreadyOwnedByYou" in payload:
        log(f"✅ MinIO: бакет '{BUCKET}' уже существует")
    else:
        sys.exit(f"❌ Не удалось создать бакет: HTTP {status}: {payload[:300]!r}")
    versioning = (b'<VersioningConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                  b"<Status>Enabled</Status></VersioningConfiguration>")
    status, payload = s3_request("PUT", f"/{BUCKET}", "versioning=", versioning)
    if status != 200:
        sys.exit(f"❌ Не удалось включить версионирование: HTTP {status}: {payload[:300]!r}")
    log("✅ MinIO: версионирование бакета включено (можно откатить state)")


# -------------------------------------------------------------------- Grafana
def gf(method, path, body=None):
    return http(method, GRAFANA + path, body, auth=ADMIN_AUTH)


def ensure_service_account():
    status, data = gf("GET", f"/api/serviceaccounts/search?query={SA_NAME}")
    if status != 200:
        sys.exit(f"❌ Grafana API вернул {status}: {data}. Проверьте GRAFANA_ADMIN_PASSWORD в .env")
    for sa in data.get("serviceAccounts", []):
        if sa["name"] == SA_NAME:
            log(f"✅ Grafana: service account '{SA_NAME}' уже есть (id={sa['id']})")
            return sa["id"]
    # Роль Admin нужна, потому что Terraform создаёт датасорсы, папки, алерты и т.д.
    # В боевой среде выдавайте минимально необходимые права (см. docs/00-overview.md).
    status, data = gf("POST", "/api/serviceaccounts", {"name": SA_NAME, "role": "Admin"})
    if status != 201:
        sys.exit(f"❌ Не удалось создать service account: {status} {data}")
    log(f"✅ Grafana: создан service account '{SA_NAME}' (id={data['id']})")
    return data["id"]


def rotate_token(sa_id):
    status, tokens = gf("GET", f"/api/serviceaccounts/{sa_id}/tokens")
    for t in tokens if status == 200 else []:
        gf("DELETE", f"/api/serviceaccounts/{sa_id}/tokens/{t['id']}")
    status, data = gf("POST", f"/api/serviceaccounts/{sa_id}/tokens", {"name": TOKEN_NAME})
    if status != 200:
        sys.exit(f"❌ Не удалось выпустить токен: {status} {data}")
    log("✅ Grafana: выпущен новый токен (старые удалены)")
    return data["key"]


def main():
    wait_until("Grafana отвечает", lambda: gf("GET", "/api/health")[0] == 200, timeout=60)
    ensure_bucket()
    token = rotate_token(ensure_service_account())

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "terraform.env")
    # Формат КЛЮЧ=ЗНАЧЕНИЕ без кавычек: его понимают make, `docker --env-file`,
    # `set -a; . файл` в bash и scripts/load-env.ps1 в PowerShell.
    lines = [
        "# Сгенерировано scripts/bootstrap.py. НЕ КОММИТИТЬ (каталог .secrets/ в .gitignore).",
        f"GRAFANA_URL={os.environ['HOST_GRAFANA_URL']}",
        f"GRAFANA_AUTH={token}",
        f"AWS_ENDPOINT_URL_S3={os.environ['HOST_MINIO_URL']}",
        f"AWS_ACCESS_KEY_ID={S3_USER}",
        f"AWS_SECRET_ACCESS_KEY={S3_PASS}",
        "AWS_REGION=us-east-1",
        "TF_IN_AUTOMATION=",
        "CHECKPOINT_DISABLE=1",
    ]
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    # 0644, а не 0600: файл создаёт root внутри контейнера, а читать его должен обычный
    # пользователь на хосте (make/terraform). Каталог .secrets/ — только для локального стенда.
    os.chmod(path, 0o644)
    log(f"✅ Записан {path} (на вашем компьютере: .secrets/terraform.env)")


if __name__ == "__main__":
    main()
