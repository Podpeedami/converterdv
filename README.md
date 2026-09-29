# Video Converter

Веб-приложение для перекодирования видео через браузер.

Стек:
- FastAPI — API и веб-интерфейс
- Celery — фоновые задачи перекодирования
- Redis — брокер и хранилище результатов Celery
- FFmpeg — перекодирование видео
- Docker Compose — запуск всех компонентов

## Возможности

- загрузка одного или нескольких видеофайлов;
- несколько файлов обрабатываются отдельными фоновыми задачами;
- отмена одной или всех выбранных перекодировок;
- прогресс перекодирования;
- пресеты разрешения:
  - `1080p` — 1920×1080, H.264;
  - `720p` — 1280×720, H.264;
  - `720p_hevc` — 1280×720, H.265/HEVC;
- форматы вывода:
  - MP4;
  - MKV;
  - WebM;
- качество: `low`, `medium`, `high`;
- после успешного перекодирования исходный файл удаляется из `data/input`;
- готовые файлы сохраняются в `data/output`;
- данные и настройки можно изменить без пересборки Docker-образа.

## Требования

На компьютере должны быть установлены:

- Docker Desktop (Windows/macOS) или Docker Engine + Docker Compose (Linux);
- доступ к GitHub Container Registry (образ опубликован как `ghcr.io/podpeedami/converterdv:latest`).

Для обычного запуска исходный код и FFmpeg устанавливать на компьютер не требуется.

## Быстрый запуск

Создайте отдельную папку для приложения и поместите в неё:

- `docker-compose.yml`
- `.env`

Скопировать пример настроек:

```bash
cp .env.example .env
```

В Windows PowerShell можно:

```powershell
Copy-Item .env.example .env
```

После этого при необходимости измените `.env`.

Запустите приложение:

```bash
docker compose up -d
```

Проверьте состояние:

```bash
docker compose ps
```

После запуска откройте в браузере:

```text
http://localhost:8080
```

Если в `.env` указан другой порт, используйте его.

## Настройки `.env`

Пример:

```env
PORT=8080
DATA_PATH=./data
MAX_UPLOAD_SIZE=10G
```

### `PORT`

Порт, на котором приложение будет доступно на хост-машине.

Например:

```env
PORT=8080
```

Тогда приложение открывается по адресу:

```text
http://localhost:8080
```

Можно изменить:

```env
PORT=9000
```

Тогда адрес будет:

```text
http://localhost:9000
```

### `DATA_PATH`

Папка на хост-машине, в которой будут храниться входные и готовые файлы.

По умолчанию:

```env
DATA_PATH=./data
```

Docker Compose использует её как `/data` внутри контейнеров.

Структура:

```text
data/
├── input/
└── output/
```

На Linux/macOS можно указать абсолютный путь:

```env
DATA_PATH=/srv/video-converter/data
```

На Windows с Docker Desktop рекомендуется использовать путь, доступный Docker Desktop, например:

```env
DATA_PATH=./data
```

### `MAX_UPLOAD_SIZE`

Максимальный суммарный размер загружаемого файла.

Например:

```env
MAX_UPLOAD_SIZE=10G
```

Поддерживаются суффиксы:

- `B` — байты;
- `K` — KiB;
- `M` — MiB;
- `G` — GiB;
- `T` — TiB.

Также можно указать число без суффикса — оно трактуется как байты.

Примеры:

```env
MAX_UPLOAD_SIZE=500M
MAX_UPLOAD_SIZE=2G
MAX_UPLOAD_SIZE=10G
```

## Остановка и запуск

Остановить контейнеры:

```bash
docker compose down
```

Запустить снова:

```bash
docker compose up -d
```

Посмотреть логи API:

```bash
docker compose logs -f api
```

Посмотреть логи worker:

```bash
docker compose logs -f worker
```

## Обновление приложения

Приложение использует готовый Docker-образ из GitHub Container Registry.

Чтобы получить последнюю опубликованную версию:

```bash
docker compose pull
```

Затем пересоздайте контейнеры:

```bash
docker compose up -d
```

Проверить состояние:

```bash
docker compose ps
```

Важно: `docker compose pull` обновляет Docker-образ, но не обновляет сам файл `docker-compose.yml`. Если `docker-compose.yml` распространяется отдельно, его нужно обновить отдельно.

## Данные

Входящие файлы:

```text
data/input/
```

Готовые файлы:

```text
data/output/
```

После успешного перекодирования исходный файл из `input` удаляется.

Redis хранит свои данные в отдельном Docker volume `redis_data`.

## Безопасность

По умолчанию приложение предназначено для запуска в локальной сети или за reverse proxy.

Если открыть порт приложения непосредственно в интернет, рекомендуется дополнительно настроить:

- HTTPS;
- reverse proxy;
- аутентификацию;
- ограничения размера и частоты запросов;
- firewall.

Не публикуйте Redis наружу: в текущем `docker-compose.yml` порт Redis не пробрасывается на хост.

## Архитектура

```text
Браузер
   │
   ▼
FastAPI (api)
   │
   ├── загрузка → /data/input
   │
   └── Celery task → Redis
                     │
                     ▼
                 worker
                     │
                     ▼
                   FFmpeg
                     │
                     ▼
              /data/output
```

API и worker используют один и тот же каталог `/data`, поэтому worker может обработать файл, который загрузил API.

## Пример структуры

```text
video-converter/
├── docker-compose.yml
├── .env
├── .env.example
└── data/
    ├── input/
    └── output/
```

Файл `.env` содержит локальные настройки и не должен добавляться в Git.

`.env.example` можно хранить в репозитории как шаблон.

## Docker-образ

Используется образ:

```text
ghcr.io/podpeedami/converterdv:latest
```

Образ публикуется через GitHub Actions.

## Лицензия

Добавьте сюда лицензию проекта, если она будет использоваться.
