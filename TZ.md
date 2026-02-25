# Техническое задание: Langflow + MinIO + кастомные S3-компоненты (vibe coding / Codex)

## 0) Цель

Нужен репозиторий/проект, который **Codex-агент** сможет воспроизводимо собрать и запустить локально:

- `MinIO` (S3-совместимое хранилище) в Docker
- `Langflow` в Docker
- Набор кастомных компонент Langflow для работы с S3 (upload/download)
- Автотесты на Python:
  - smoke/roundtrip тесты MinIO (через boto3)
  - тесты кастомных компонент (S3 upload/download) против MinIO
  - (опционально) smoke тест Langflow API (health + наличие компонент)

Приоритет: быстрый цикл разработки компонентов (правка → тесты → UI).

## 1) Источники/контракты Langflow (ориентир для реализации)

- Custom components: inputs/outputs, структура Component, Output(method=...)  
  https://docs.langflow.org/components-custom-components
- Environment variables: `LANGFLOW_COMPONENTS_PATH`, `LANGFLOW_AUTO_LOGIN`, etc.  
  https://docs.langflow.org/environment-variables
- File management (контракт file_path, storage backend local/S3)  
  https://docs.langflow.org/concepts-file-management
- Files API endpoints (upload/delete)  
  https://docs.langflow.org/api-files
- Troubleshoot (важно: `__init__.py` в папках категорий компонент, и fallback на `--components-path`)  
  https://docs.langflow.org/troubleshoot
- Containerize Langflow (как паковать custom components в Docker)  
  https://docs.langflow.org/develop-application

## 2) Требования к структуре проекта

В корне должен быть `docker-compose.yml` и папка `services/`, где каждый сервис живёт в своей подпапке
со своим `.env` и `.env.example`.

Пример целевой структуры:

```text
.
+-- docker-compose.yml
+-- services
|   +-- minio
|   |   +-- .env.example
|   |   +-- init
|   |       +-- minio-init.sh
|   +-- langflow
|       +-- .env.example
|       +-- Dockerfile
|       +-- components
|       |   +-- s3
|       |       +-- __init__.py
|       |       +-- s3_upload.py
|       |       +-- s3_download.py
|       +-- tests
|           +-- test_s3_components.py
+-- tests
    +-- .env.example
    +-- requirements.txt
    +-- test_minio_s3.py
    +-- test_langflow_api.py
```

**Запреты:**
- Никаких хардкодов секретов/паролей/ключей в коде и compose.
- Все конфиги — через `.env` и `.env.example`.

## 3) Docker Compose: MinIO

### 3.1. Контейнер minio
Требования:
- Порты:
  - S3 API: `9000:9000`
  - Console: `9001:9001`
- Персистентность: volume для `/data`
- Переменные окружения — из `services/minio/.env`

### 3.2. Инициализация MinIO (обязательное)
После старта MinIO нужно автоматически:
- создать бакет `MINIO_BUCKET`
- создать S3-пользователя (access/secret) `MINIO_S3_USER` / `MINIO_S3_PASSWORD`
- выдать ему доступ RW **только** к `MINIO_BUCKET`

Рекомендуемый способ:
- отдельный сервис `minio-init` на базе `minio/mc`
- скрипт `services/minio/init/minio-init.sh`, который:
  1) ждёт готовности minio
  2) создаёт bucket
  3) создаёт policy (bucket-only)
  4) создаёт user
  5) attach policy

### 3.3. Переменные `.env` для MinIO
`services/minio/.env.example` должен включать:
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`
- `MINIO_S3_USER`
- `MINIO_S3_PASSWORD`
- `MINIO_BUCKET`
- `MINIO_REGION` (например `us-east-1`)

## 4) Docker Compose: Langflow

Требования:
- Порт: `7860:7860`
- Минимальная настройка для входа в UI:
  - dev-режим без логина через `LANGFLOW_AUTO_LOGIN=true` (только для локалки)
    (см. env vars/аутентификация в Langflow docs)
- Подключить кастомные компоненты:
  - установить `LANGFLOW_COMPONENTS_PATH` на путь, где лежит `components/`
  - компоненты должны загружаться при старте
  - в папке каждой категории компонент должен быть `__init__.py` (иначе Python не увидит модуль)

### 4.1. Langflow Dockerfile
Собрать кастомный образ на основе официального `langflowai/langflow`.
Обязательные зависимости:
- `aioboto3` (для async S3)
- `pytest` (для тестов в контейнере)

## 5) Кастомные компоненты: требования к функционалу

Компоненты должны быть **совместимы с MinIO** через `endpoint_url`.

### 5.1. Компонента `S3Upload`
Назначение: загрузка файла/картинки в S3.

**Inputs (UI):**
- `endpoint_url` (string, required)
- `access_key` (secret/password, required)
- `secret_key` (secret/password, required)
- `session_token` (secret/password, optional, advanced)
- `region` (string, default `us-east-1`, advanced)
- `bucket` (string, required)
- `object_key` (string, required) — путь в бакете (например `images/abc.png`)
- `input_mode` (dropdown: `auto|file|base64`, default `auto`)
- `file` (FileInput, optional)
- `data` (DataInput, optional) — base64 или data_url

**Поведение:**
- `auto`: если есть `file` — грузить файл по пути; иначе ожидать `data`
- `file`: обязателен `file`
- `base64`: обязателен `data`, поддержать:
  - `{"base64": "<...>"}` и/или `{"data_url": "data:image/png;base64,<...>"}`

**Output:**
- `Data` с полями:
  - `bucket`, `key`, `size_bytes`, `etag` (если есть), `s3_uri`
  - `filename` (если известно)

**Async:**
- использовать `aioboto3` или не блокировать event loop.

### 5.2. Компонента `S3Download`
Назначение: скачать файл/картинку из S3 и вернуть либо base64, либо временный локальный путь.

**Inputs (UI):**
- `endpoint_url`, `access_key`, `secret_key`, `session_token`, `region`
- `bucket` (required)
- `object_key` (required)
- `return_mode` (dropdown: `base64|temp_file`, default `temp_file`)
- `temp_dir` (string, optional, advanced) — куда писать temp-файлы
- `include_data_url` (bool, advanced) — если `base64` и mime=image/*, добавить data_url

**Поведение:**
- `base64`: вернуть `Data(base64=..., mime=..., filename=..., [data_url])`
- `temp_file`: записать bytes во временный файл (в `temp_dir` или системный temp),
  вернуть `Data(file_path=<path>, filename=<name>)`
  - это нужно для downstream нод, которые принимают `FileInput` (OCR)

**Важно по жизненному циклу temp_file:**
- temp-файл нужен только на время исполнения flow.
- Поэтому требуется стратегия очистки (см. пункт 6).

## 6) Очистка временных файлов (обязательное решение)

Нужно реализовать один из вариантов (можно оба):

### Вариант A (предпочтительно): отдельная компонента `DeleteLocalFiles`
- Input: `DataInput` с `file_path` или `file_paths`
- Output: `Data` со списком удалённых/ошибок
- Использование: ставится в конце ветки после OCR/обработки

### Вариант B: очистка внутри OCR/Read File
- Если используется стандартная `Read File` нода, учесть что она поддерживает
  `delete_server_file_after_processing` (по умолчанию true) — но это относится к server file,
  а не к arbitrary `/tmp/...`.
  Поэтому для `/tmp` всё равно нужен `DeleteLocalFiles` или удаление в OCR.

## 7) Тестирование

### 7.1. Тесты MinIO (host tests)
В папке `tests/`:
- `requirements.txt`: pytest, boto3, requests, python-dotenv
- `test_minio_s3.py`:
  1) проверить доступ к бакету (list_buckets / наличие test bucket)
  2) put/get/delete roundtrip для произвольного key

Все параметры подключения — из `tests/.env` (пример в `.env.example`):
- `TEST_MINIO_ENDPOINT_URL` (например `http://localhost:9000`)
- `TEST_MINIO_ACCESS_KEY`
- `TEST_MINIO_SECRET_KEY`
- `TEST_MINIO_BUCKET`
- `TEST_MINIO_REGION`

### 7.2. Тесты кастомных компонент (внутри контейнера Langflow)
В `services/langflow/tests/test_s3_components.py`:
- создать bucket если его нет (boto3)
- прогнать roundtrip:
  - S3Upload (base64) -> S3Download (base64) и сравнить payload
- тест должен читать MinIO конфиг из env (в docker-compose прокинуть `TEST_MINIO_*` в langflow)

### 7.3. Smoke тест Langflow API (host tests)
`tests/test_langflow_api.py`:
- дождаться `/health` = 200
- запросить список компонент (например `GET /api/v1/all`) и убедиться, что `S3 Upload` и `S3 Download` видны.
Примечание: Files endpoints требуют API key; для dev можно отключить/обойти auth через AUTO_LOGIN,
но тест должен поддерживать и режим с `LANGFLOW_API_KEY` (если задан).

## 8) Скрипты / удобство

Добавить `scripts/`:
- `up.sh`: копирует `.env.example -> .env` если нет, затем `docker compose up -d --build`
- `test.sh`: запускает host tests + container tests

## 9) Acceptance criteria

Успех считается достигнутым, если:

1) `docker compose up -d --build` поднимает MinIO + init + Langflow без ошибок.
2) В MinIO создан bucket и пользователь S3 с RW доступом только к bucket.
3) Langflow UI доступен на `http://localhost:7860`.
4) Кастомные компоненты S3 отображаются в UI и доступны для добавления в flow.
5) `pytest` в `tests/` проходит (MinIO + Langflow API smoke).
6) `pytest` внутри контейнера Langflow проходит (roundtrip кастомных компонент).

---
