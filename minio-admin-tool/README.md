MinIO Admin Tool

Тут лежит изолированный стенд для создания пользователя, бакета, политики и лимитов в MinIO через `mc`.

Что нужно перед запуском:
- `cp .env.example .env` (если `.env` еще нет)
- заполнить реальные креды в `.env`

Важно:
- файл можно запускать без execute-права через `bash`
- если у тебя уже есть внешний MinIO, локальный `minio` в compose запускать не нужно

Запуск (копируй как есть):

1. Локальный запуск (поднимает контейнер minio из compose и настраивает его):

`cd /Users/hdp02/langflow_test/minio-admin-tool && MC_MODE=local bash run.sh`

2. Внешний MinIO (не поднимаем локальный контейнер):

1) В `.env` задай параметры внешнего MinIO:
- `MINIO_HOST=<REMOTE_MINIO_HOST>:9000`
- `MINIO_ROOT_USER=<ROOT_USER>`
- `MINIO_ROOT_PASSWORD=<ROOT_PASSWORD>`
- `MINIO_S3_USER=<S3_USER>`
- `MINIO_S3_PASSWORD=<S3_PASSWORD>`
- `MC_MODE=remote`

2) Запусти:

`cd /Users/hdp02/langflow_test/minio-admin-tool && bash run.sh`

Или просто вручную отредактируй `.env` и выполни:

`cd /Users/hdp02/langflow_test/minio-admin-tool && MC_MODE=remote bash run.sh`

Альтернативно можно передать режим аргументом:

`bash /Users/hdp02/langflow_test/minio-admin-tool/run.sh local`

`bash /Users/hdp02/langflow_test/minio-admin-tool/run.sh remote`

Дополнительно, чтобы “с нуля” на локальном стенде (с очисткой тома):

`cd /Users/hdp02/langflow_test/minio-admin-tool && docker compose down -v && MC_MODE=local bash run.sh`
