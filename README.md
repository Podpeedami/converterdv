# Video Converter

Веб-приложение для перекодирования видео.

Использует:

- FastAPI — веб-интерфейс и API
- Celery — фоновые задачи
- Redis — очередь задач
- FFmpeg — перекодирование видео
- Docker — запуск приложения

## Возможности

- загрузка одного или нескольких видеофайлов;
- одновременная обработка нескольких файлов;
- выбор формата результата: MP4, WebM, MKV;
- выбор разрешения: 1080p, 720p, 720p HEVC;
- выбор качества: Low, Medium, High;
- отображение прогресса перекодирования;
- отмена отдельных задач;
- отмена всех выбранных задач;
- автоматическое удаление исходного файла после успешного перекодирования;
- ограничение размера загружаемого файла;
- данные хранятся на диске пользователя.

## Быстрый запуск

### Требования

Необходимы Docker Desktop и Docker Compose.

Проверить Docker:

```bash
docker --version
docker compose version
```

## Запуск

Скачайте проект и перейдите в его каталог:

```bash
cd video-converter
```

Запустите приложение:

```bash
docker compose up -d
```

После запуска откройте:

```text
http://localhost:8080
```

## Остановка

```bash
docker compose down
```

Запуск снова:

```bash
docker compose up -d
```

## Обновление

```bash
docker compose pull
docker compose up -d
```

## Проверка состояния

```bash
docker compose ps
```

Логи:

```bash
docker compose logs
```

Логи API:

```bash
docker compose logs api
```

Логи worker:

```bash
docker compose logs worker
```

Логи Redis:

```bash
docker compose logs redis
```

## Хранение файлов

Все входные и выходные видео находятся в каталоге:

```text
./data
```

Структура:

```text
data/
├── input/
└── output/
```

В Docker этот каталог подключается как:

```text
./data:/data
```

Исходные видео помещаются в `data/input/`.

Готовые видео появляются в `data/output/`.

После успешного перекодирования исходный файл автоматически удаляется из `data/input/`.

## Настройки

Основные настройки находятся непосредственно в `docker-compose.yml`.

### Порт

По умолчанию:

```yaml
ports:
  - "8080:8000"
```

Веб-интерфейс:

```text
http://localhost:8080
```

Чтобы использовать другой порт, например `9000`:

```yaml
ports:
  - "9000:8000"
```

После изменения:

```bash
docker compose up -d
```

### Максимальный размер загрузки

По умолчанию:

```yaml
- MAX_UPLOAD_SIZE=10G
```

Например:

```yaml
- MAX_UPLOAD_SIZE=20G
```

Поддерживаются значения:

```text
500M
2G
10G
1.5G
```

### Каталог данных

По умолчанию:

```yaml
volumes:
  - ./data:/data
```

При необходимости можно изменить путь:

```yaml
volumes:
  - D:/Videos/converter:/data
```

## Docker-контейнеры

Приложение состоит из трёх контейнеров.

### API

```text
video-api
```

Отвечает за веб-интерфейс, загрузку файлов, создание задач, получение статуса задач и скачивание результатов.

### Worker

```text
video-worker
```

Выполняет перекодирование видео с помощью FFmpeg.

По умолчанию запускается два параллельных процесса:

```text
--concurrency=2
```

### Redis

```text
video-redis
```

Используется как очередь задач Celery.

Данные Redis сохраняются в Docker volume `redis_data`.

## Архитектура

```text
Browser
   │
   ▼
API (FastAPI)
   │
   ▼
Redis
   │
   ▼
Celery Worker
   │
   ▼
FFmpeg
   │
   ├── data/input
   │
   └── data/output
```

## Docker Compose

Основная конфигурация находится в одном файле `docker-compose.yml`.

Полная конфигурация:

```yaml
services:
  api:
    image: ghcr.io/podpeedami/converterdv:latest
    container_name: video-api

    environment:
      - REDIS_URL=redis://redis:6379/0
      - MAX_UPLOAD_SIZE=10G

    volumes:
      - ./data:/data

    ports:
      - "8080:8000"

    depends_on:
      - redis

    restart: unless-stopped

  worker:
    image: ghcr.io/podpeedami/converterdv:latest
    container_name: video-worker

    command: >
      celery
      -A app.celery_app.celery_app
      worker
      --loglevel=info
      --concurrency=2

    environment:
      - REDIS_URL=redis://redis:6379/0

    volumes:
      - ./data:/data

    depends_on:
      - redis

    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: video-redis

    command: redis-server --appendonly yes

    volumes:
      - redis_data:/data

    restart: unless-stopped

volumes:
  redis_data:
```

## Полезные команды

Запуск:

```bash
docker compose up -d
```

Остановка:

```bash
docker compose down
```

Перезапуск:

```bash
docker compose restart
```

Обновление:

```bash
docker compose pull
docker compose up -d
```

Статус:

```bash
docker compose ps
```

Логи:

```bash
docker compose logs -f
```

## Docker Image

Проект использует Docker image:

```text
ghcr.io/podpeedami/converterdv:latest
```

При обновлении проекта:

```bash
docker compose pull
docker compose up -d
```

## Разработка

Исходный код находится в каталоге `app/`.

```text
app/
├── main.py
├── celery_app.py
├── tasks.py
└── static/
    └── index.html
```

## Лицензия

Проект предоставляется для использования и дальнейшего развития.
