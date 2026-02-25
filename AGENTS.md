# Codex Agent Instructions (place this file at repo root as `AGENTS.md`)

Ты — агент, который должен реализовать проект по ТЗ `TZ.md`.

## Принципы
- Никакого хардкода секретов. Только `.env` + `.env.example`.
- Все сервисы в `services/<service_name>/`.
- Все команды и пути — воспроизводимы.
- При проблемах с загрузкой компонент:
  - проверь `__init__.py` в папках категорий
  - проверь `LANGFLOW_COMPONENTS_PATH`
  - попробуй запуск Langflow с `--components-path` (см. troubleshoot docs)

## План работ (с чеклистом)

### 1) Структура проекта
- [ ] Создать структуру папок из ТЗ
- [ ] Добавить `.gitignore` (игнорировать реальные `.env`, `.venv`, `__pycache__`)

### 2) Docker Compose
- [ ] `docker-compose.yml` с сервисами: `minio`, `minio-init`, `langflow`
- [ ] volumes для данных minio и langflow
- [ ] сеть (bridge) общая для сервисов

### 3) MinIO
- [ ] `services/minio/.env.example` с нужными переменными
- [ ] `services/minio/init/minio-init.sh`:
  - ждёт готовности
  - создаёт bucket
  - создаёт policy ограниченную bucket
  - создаёт S3 user и attach policy
- [ ] В compose подключить init-скрипт и env

### 4) Langflow
- [ ] `services/langflow/.env.example`:
  - `LANGFLOW_AUTO_LOGIN=true` (dev)
  - `LANGFLOW_COMPONENTS_PATH=/app/components` (или другой путь)
  - `LANGFLOW_CONFIG_DIR=/app/data`
- [ ] `services/langflow/Dockerfile`:
  - базовый образ `langflowai/langflow`
  - установить `aioboto3` и `pytest`
- [ ] В compose:
  - пробросить порт 7860
  - смонтировать `components/` в контейнер (или COPY в image)
  - при необходимости пробросить `TEST_MINIO_*` env в langflow контейнер для тестов

### 5) Кастомные компоненты S3
- [ ] Реализовать `S3Upload` и `S3Download` по ТЗ:
  - inputs через `lfx.io` (SecretStrInput/FileInput/DataInput/etc.)
  - outputs через `Output(method=...)`
  - async совместимость (aioboto3 или to_thread)
- [ ] Убедиться что в `components/s3/__init__.py` существует

### 6) Cleanup
- [ ] Реализовать `DeleteLocalFiles` или иной механизм очистки temp файлов

### 7) Тесты
- [ ] Host tests:
  - `tests/requirements.txt`
  - `tests/.env.example`
  - `test_minio_s3.py`, `test_langflow_api.py`
- [ ] Container tests:
  - `services/langflow/tests/test_s3_components.py`
  - roundtrip upload->download (base64) против MinIO

### 8) Скрипты
- [ ] `scripts/up.sh`
- [ ] `scripts/test.sh`

## Команды, которые агент обязан прогонять
```bash
# поднять стенд
docker compose up -d --build

# host tests
cd tests
cp -n .env.example .env || true
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
cd ..

# container tests
docker compose exec -T langflow python -m pytest -q
```

## Definition of Done
- Все пункты Acceptance criteria из `TZ.md` выполнены.
