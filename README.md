# Langflow + MinIO S3 Components

## Что это

Набор для локальной разработки/проверки кастомных S3-компонентов Langflow с MinIO.

Композиция:
- `minio` — локальный S3-совместимый бакет.
- `minio-init` — bootstrap-инициализация бакета, пользователя и policy.
- `langflow` — запускается с подключённым каталогом компонентов `services/langflow/components`.

## docker-compose

- Все сервисы в `platform` сети (bridge), тома используются для данных MinIO.
- `minio` публикует:
  - `9000:9000` (S3 API)
  - `9001:9001` (консоль)
- `minio-init` запускается one-shot после `minio` и делает:
  - ожидание доступности
  - создание бакета `MINIO_BUCKET`
  - создание policy `s3-<bucket>-rw`
  - создание/привязку пользователя `MINIO_S3_USER`
  - загрузку seed-изображений из `./images` в `<bucket>/images/`
- `langflow` запускается после успешного завершения `minio-init`.

## Компоненты S3

### `S3Upload`

- Загружает **один** объект в S3/MinIO.
- Вход: `DataInput` с полями:
  - `name` — имя файла
  - `base64` — содержимое в base64
  - `folder` — папка в бакете (`/` — корень)
  - `mime` — optional
- Выходы:
  - `result` — `Data({"bucket": ..., "key": "folder/file.txt", "size_bytes": ..., "etag": ..., "mime": ...})`

### `S3Download`

- Скачивает объект и возвращает строго base64.
- Вход: `Message File Reference` + credentials:
  - `message_file_reference` (`MessageText`) — текстовое сообщение с путём к объекту
- Выход: `Data({"bucket": ..., "key": ..., "base64": ..., "mime": ..., "size_bytes": ...})`
- Для пайплайна `Upload -> Download` передавайте `S3Upload.result["key"]` (или полный объект `S3Upload.result`) в `S3Download.message_file_reference`.

### `S3UploadBase`

- Загружает несколько локальных файлов.
- Вход:
  - `files` — один/много путей
  - `s3_folder` — целевая папка
- Выход: `Data({"folder": ..., "files": [...]})`

### `S3ListFiles`

- Возвращает список ключей объектов внутри папки.
- Вход: `folder`
- Выход: `Data({"folder": ..., "files": ["folder/file.png", ...]})`

### `DeleteLocalFiles`

- Удаляет локальные пути файлов из `files_data` (`file_path`/`file_paths`/`paths`).

## Как пользоваться тестами (кратко)

### Что покрыто

- Unit-тесты компонентов (`ComponentTestBaseWithoutClient`):
  - `S3Upload` (`services/langflow/tests/unit/components/s3/test_s3_upload.py`)
  - `S3Download` (`services/langflow/tests/unit/components/s3/test_s3_download.py`)
  - `S3UploadBase` (`services/langflow/tests/unit/components/s3/test_s3_upload_base.py`)
  - `S3ListFiles` (`services/langflow/tests/unit/components/s3/test_s3_list.py`)
  - `DeleteLocalFiles` (`services/langflow/tests/unit/components/s3/test_delete_local_files.py`)
  - В этих тестах моки aioboto3, проверяется `await component_instance.run()`, включая:
    - успешный happy path,
    - ошибки ввода,
    - негативные кейсы S3 (bad credentials/timeout/NotFound),
    - контрактные поля результата (`bucket`, `key`, `files`, и т.д.).

- Проверка контракта Data (`integration`):
  - `services/langflow/tests/integration/test_s3_data_contract.py`
  - Проверяет связки компонентов и передачу Data без сериализационных расхождений:
    - `S3Upload -> S3Download` (roundtrip base64),
    - `S3Upload -> S3ListFiles` (поиск загруженного ключа).

- Проверка механики output-методов:
  - `services/langflow/tests/unit/test_output_dispatch.py`
  - Проверяет, что async output вызывается через `await`,
    sync output — через `asyncio.to_thread`.

- E2E через API Langflow:
  - `services/langflow/tests/e2e/test_langflow_api_flow.py`
  - Загружает flow из `services/langflow/tests/fixtures/s3_roundtrip_flow.json`,
    затем запускает `/api/v1/run/{flow_id}` (и альтернативные пути через fallback),
    проверяет, что API возвращает результат.

### Структура тестов

- `services/langflow/tests/helpers/` — общие фикстуры/фиктивный S3-слой:
  - `component_test_base.py`
  - `s3_fakes.py`
- `services/langflow/tests/unit/` — unit-уровень
- `services/langflow/tests/integration/` — интеграционные контракты компонентов
- `services/langflow/tests/e2e/` — e2e сценарий API
- `services/langflow/tests/fixtures/` — JSON flow для e2e

## Запуск

### 1) Подготовка env

```bash
cp -n services/minio/.env.example services/minio/.env
cp -n services/langflow/.env.example services/langflow/.env
cp -n tests/.env.example tests/.env
```

### 2) Поднять сервисы

```bash
docker compose up -d --build
```

### 3) Проверка состояния

```bash
docker compose ps
docker compose logs -f minio
docker compose logs -f langflow
```

### 4) Полный сценарий через скрипт

```bash
bash scripts/up.sh
```

## Тестирование (только снаружи контейнеров)

### Host tests (предпочтительно)

```bash
cd tests
cp -n .env.example .env || true
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run pytest -q
```

### Тесты внутри контейнера Langflow (рекомендуемый путь после контейнерного старта)

```bash
docker compose up -d --build
docker compose exec -T langflow python -m pytest -q
```

Для отдельного запуска уровней:

```bash
docker compose exec -T langflow python -m pytest -q services/langflow/tests/unit
docker compose exec -T langflow python -m pytest -q services/langflow/tests/integration
docker compose exec -T langflow python -m pytest -q services/langflow/tests/e2e
```

### Быстрый host-only прогон только новых unit/integration тестов (без API)

```bash
cd services/langflow
python -m pytest -q tests/unit tests/integration
```

> Для host-only запуска используйте Python-окружение с зависимостями `lfx`, `pytest` и др., как в `services/langflow/Dockerfile`.

### E2E переменные окружения

- `TEST_LANGFLOW_BASE_URL` (по умолчанию `http://localhost:7860`)
- `TEST_FLOW_FIXTURE_PATH` (по умолчанию `services/langflow/tests/fixtures/s3_roundtrip_flow.json`)
- `TEST_LANGFLOW_API_KEY` (опционально)

## Примечание по старым тестам

Скрипты в корне `tests/` (`tests/test_minio_s3.py`, `tests/test_langflow_api.py`) оставлены как smoke/инфраструктурные проверки для поднятой среды, но основной компонентный контроль теперь реализован через `services/langflow/tests/*`.

## Управление сервисами

```bash
docker compose down
docker compose down -v
docker compose up -d --build
```
