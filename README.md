# Video Converter — Docker Compose

Веб-приложение для перекодирования видео на базе:

- FastAPI — веб-интерфейс и API
- Celery — очередь и выполнение задач
- Redis — брокер задач
- FFmpeg — перекодирование видео
- Docker Compose — запуск всех компонентов

## 1. Что нужно установить

На сервере должен быть установлен Docker с поддержкой Docker Compose.

Проверка:

```bash
docker --version
docker compose version
```

---

# 2. Готовый docker-compose.yml

Создайте файл:

```text
docker-compose.yml
```

и вставьте в него:

```yaml
services:
  api:
    image: ghcr.io/podpeedami/converterdv:latest
    container_name: video-api

    environment:
      - REDIS_URL=redis://redis:6379/0
      - MAX_UPLOAD_SIZE=10G

    volumes:
      - /mnt/videos:/data

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
      - /mnt/videos:/data

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

---

# 3. Важный момент: volumes у api и worker

Это **самая важная настройка**, если видео хранятся не в стандартной `./data`.

У `api` и `worker` обязательно должна быть подключена **одна и та же папка сервера**.

Правильно:

```yaml
api:
  volumes:
    - /mnt/videos:/data

worker:
  volumes:
    - /mnt/videos:/data
```

Здесь:

```text
/mnt/videos
```

— папка на сервере.

А:

```text
/data
```

— папка внутри Docker-контейнера.

Оба контейнера должны видеть один и тот же `/mnt/videos`.

### Почему это необходимо

`api` принимает загруженный файл и сохраняет его:

```text
/data/input/имя-файла.mp4
```

Затем Celery `worker` получает задачу и FFmpeg пытается открыть тот же файл:

```text
/data/input/имя-файла.mp4
```

Если `api` и `worker` используют разные папки хоста, worker не найдёт файл.

В таком случае появляется ошибка:

```text
Error opening input file /data/input/...
No such file or directory
```

Поэтому при изменении папки видео **всегда меняйте volume одновременно у `api` и `worker`**.

---

# 4. Подготовка папки для видео

В данном примере используется:

```text
/mnt/videos
```

Создайте необходимые каталоги:

```bash
mkdir -p /mnt/videos/input
mkdir -p /mnt/videos/output
```

В результате:

```text
/mnt/videos/
├── input/
└── output/
```

Исходные загруженные видео находятся в:

```text
/mnt/videos/input/
```

Готовые видео появляются в:

```text
/mnt/videos/output/
```

После успешного перекодирования исходный файл удаляется из `input`.

---

# 5. Если нужна другая папка

Например, вместо `/mnt/videos` нужно использовать:

```text
/home/videos
```

Тогда **в обоих контейнерах** нужно изменить volume:

```yaml
api:
  volumes:
    - /home/videos:/data

worker:
  volumes:
    - /home/videos:/data
```

Нельзя менять только `api` или только `worker`.

---

# 6. Запуск

Перейдите в папку проекта:

```bash
cd ~/video-converter
```

Проверьте конфигурацию:

```bash
docker compose config
```

Если ошибок нет, запустите:

```bash
docker compose up -d
```

Проверьте контейнеры:

```bash
docker compose ps
```

Должны работать:

```text
video-api
video-worker
video-redis
```

---

# 7. Проверка папки внутри контейнеров

Проверить `api`:

```bash
docker exec video-api ls -la /data/input
```

Проверить `worker`:

```bash
docker exec video-worker ls -la /data/input
```

Оба контейнера должны видеть одну и ту же папку.

Также можно проверить output:

```bash
docker exec video-api ls -la /data/output
docker exec video-worker ls -la /data/output
```

---

# 8. Открытие сайта

По умолчанию используется:

```yaml
ports:
  - "8080:8000"
```

Это означает:

```text
порт сервера: 8080
порт приложения внутри Docker: 8000
```

Открывать сайт нужно:

```text
http://SERVER_IP:8080
```

Например:

```text
http://192.168.1.100:8080
```

---

# 9. Изменение внешнего порта

Если порт `8080` занят, можно использовать другой.

Например:

```yaml
ports:
  - "9000:8000"
```

Тогда сайт будет доступен:

```text
http://SERVER_IP:9000
```

Порт внутри контейнера `8000` менять не нужно.

---

# 10. Максимальный размер загружаемого файла

В `api` указано:

```yaml
environment:
  - MAX_UPLOAD_SIZE=10G
```

Это означает максимальный размер одного загружаемого файла — 10 GB.

Можно изменить:

```yaml
- MAX_UPLOAD_SIZE=20G
```

или:

```yaml
- MAX_UPLOAD_SIZE=500M
```

После изменения необходимо перезапустить контейнеры:

```bash
docker compose down
docker compose up -d
```

---

# 11. Worker и количество одновременных задач

В worker используется:

```yaml
--concurrency=2
```

Это означает, что worker может одновременно выполнять до двух задач перекодирования.

Если сервер мощнее, значение можно увеличить, например:

```yaml
--concurrency=4
```

Но перекодирование видео активно использует CPU, поэтому слишком большое значение может сильно увеличить нагрузку на сервер.

---

# 12. Redis

Redis используется для передачи задач между API и worker.

В `api`:

```yaml
REDIS_URL=redis://redis:6379/0
```

В `worker` используется тот же Redis:

```yaml
REDIS_URL=redis://redis:6379/0
```

Контейнер называется:

```text
video-redis
```

Данные Redis сохраняются в Docker volume:

```text
redis_data
```

Поэтому Redis не теряет свои данные просто при пересоздании контейнера.

---

# 13. Форматы видео

Поддерживаются:

```text
MP4
WebM
MKV
```

---

# 14. Разрешение видео

Доступны пресеты:

```text
1080p
720p
720p HEVC / H.265
```

Видео масштабируется с сохранением пропорций и помещается в выбранное разрешение.

---

# 15. Качество

Доступны:

```text
Low
Medium
High
```

Чем выше качество, тем больше может быть размер готового файла и время перекодирования.

---

# 16. Отмена перекодирования

Для каждой задачи предусмотрена отмена.

При отмене:

- FFmpeg останавливается
- незавершённый output удаляется
- исходный input удаляется
- задача получает статус `cancelled`

Для нескольких файлов можно отменить все выбранные задачи.

---

# 17. Что происходит при загрузке видео

Общая схема:

```text
Браузер
   ↓
API
   ↓
/mnt/videos/input/
   ↓
Redis
   ↓
Celery Worker
   ↓
FFmpeg
   ↓
/mnt/videos/output/
```

После успешного завершения:

```text
/mnt/videos/input/
```

очищается от исходного обработанного файла.

---

# 18. Обновление приложения

Образ приложения хранится в GitHub Container Registry:

```text
ghcr.io/podpeedami/converterdv:latest
```

Чтобы получить последнюю версию образа:

```bash
docker compose pull
```

Затем пересоздать контейнеры:

```bash
docker compose up -d
```

Проверить:

```bash
docker compose ps
```

---

# 19. Просмотр логов

Логи API:

```bash
docker logs video-api
```

Логи worker:

```bash
docker logs video-worker
```

Логи Redis:

```bash
docker logs video-redis
```

Следить за логами worker в реальном времени:

```bash
docker logs -f video-worker
```

Для выхода из просмотра логов нажмите:

```text
Ctrl+C
```

---

# 20. Остановка

Остановить контейнеры:

```bash
docker compose down
```

Запустить снова:

```bash
docker compose up -d
```

Остановка контейнеров не удаляет:

```text
/mnt/videos
```

и Docker volume:

```text
redis_data
```

---

# 21. Полезная проверка после изменения volumes

После изменения пути к видео рекомендуется проверить три вещи.

### 1. Папка существует на сервере

```bash
ls -la /mnt/videos
```

### 2. API видит input

```bash
docker exec video-api ls -la /data/input
```

### 3. Worker видит тот же input

```bash
docker exec video-worker ls -la /data/input
```

Если API и worker видят разные файлы, значит `volumes` настроены неправильно.

---

# 22. Главное правило

Если меняете место хранения видео:

```text
/mnt/videos
```

на другую папку, например:

```text
/home/my-videos
```

изменяйте **оба** сервиса:

```yaml
api:
  volumes:
    - /home/my-videos:/data

worker:
  volumes:
    - /home/my-videos:/data
```

`api` и `worker` должны всегда иметь одинаковое подключение:

```text
HOST_FOLDER:/data
```

Именно это обеспечивает доступ worker к файлам, которые загрузил API.
