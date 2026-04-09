# ds-expedition-infra

Infrastructure for **Expedition DS. Scanning** competition.

---

## VM

| Param | Value |
|---|---|
| Host | `212.74.224.231` |
| SSH port | `22022` |
| User | `root` / `mlops` |
| OS | Ubuntu 24.04 LTS |
| Key | `~/.ssh/selectel_ds_scan` |
| Private IP | `192.168.0.239` |
| Region | Selectel ru-7 (Москва) |

```bash
ssh -i ~/.ssh/selectel_ds_scan -p 22022 root@212.74.224.231
```

---

## ML Stack

Сервисы запущены в Docker Compose на VM (`/opt/ml-stack/`).

| Service | Port | Description |
|---|---|---|
| MLflow | `192.168.0.239:5000` | Experiment tracking |
| MinIO API | `192.168.0.239:9000` | S3 (artifacts, DVC, datasets) |
| MinIO Console | `192.168.0.239:9001` | UI (только через SSH tunnel) |
| JupyterLab | `127.0.0.1:8888` | Dev notebooks (только через SSH tunnel) |

### Доступ через SSH tunnel

```bash
ssh -i ~/.ssh/selectel_ds_scan -p 22022 \
  -L 5000:localhost:5000 \
  -L 9001:localhost:9001 \
  -L 8888:localhost:8888 \
  root@212.74.224.231
```

### MinIO бакеты

| Bucket | Назначение |
|---|---|
| `mlflow-artifacts` | MLflow артефакты |
| `dvc-remote` | DVC remote |
| `datasets` | Обучающая выборка |
| `checkpoints` | Чекпоинты моделей |
| `submissions` | Готовые сабмиты |

### Управление стеком

```bash
cd /opt/ml-stack
docker compose up -d       # Запуск
docker compose ps          # Статус
docker compose logs -f     # Логи
```

---

## Self-hosted GitHub Runners

| Runner | Репо | Директория | Сервис | Управление |
|---|---|---|---|---|
| `gpu-ml-01` | `nkz-soft/expedition-ds-scaning` | `/opt/actions-runner/` | `actions.runner.nkz-soft-expedition-ds-scaning.gpu-ml-01` | Ansible |
| `gpu-ml-baseline-01` | `nkz-soft/expedition-ds-scaning-baseline` | `/opt/actions-runner-baseline/` | `actions.runner.nkz-soft-expedition-ds-scaning-baseline.gpu-ml-baseline-01` | Ansible |

Оба раннера управляются через Ansible. Директория задаётся параметром `dir` (по умолчанию `/opt/github-runners/<name>/`).

```yaml
# В workflow указывать:
runs-on: [self-hosted, linux, gpu-orchestrator]
```

```bash
# Статус всех раннеров
systemctl status 'actions.runner.*'

# Перезапуск раннера
cd /opt/actions-runner && sudo ./svc.sh stop && sudo ./svc.sh start
cd /opt/actions-runner-baseline && sudo ./svc.sh stop && sudo ./svc.sh start
```

### Добавление нового раннера

1. В репо на GitHub: **Settings → Actions → Runners → New self-hosted runner** — скопировать токен.

2. Добавить запись в `ansible/playbooks/setup-github-runner.yml`:
   ```yaml
   - name: "my-runner"
     repo_url: "https://github.com/org/repo"
     token: "{{ runner_token_myrunner }}"
     labels: "self-hosted,linux,gpu"
   ```

3. Запустить плейбук:
   ```bash
   ansible-playbook \
     -i ansible/inventories/production/hosts.yml \
     ansible/playbooks/setup-github-runner.yml \
     -e "runner_token_baseline=<TOKEN>" \
     -e "runner_token_myrunner=<TOKEN>"
   ```

> **Примечание:** токен действует ~1 час. Роль идемпотентна — уже установленные раннеры пропускаются.

---

## Train Workflow (`.github/workflows/train.yml`)

Workflow в репо `nkz-soft/expedition-ds-scaning`. Файл хранится здесь для истории.

**Триггер:** push тега `v*` или `workflow_dispatch`

**Что делает:**
1. Runner на main VM получает job
2. Создаёт GPU VM в Selectel ru-7 через API
3. Ждёт готовности VM (~3 мин)
4. Синкает датасет из MinIO → GPU VM
5. Запускает `train.py` (MLflow логи → `192.168.0.239:5000`)
6. Артефакты → MinIO `checkpoints/<tag>/`
7. **Всегда** удаляет GPU VM (даже при ошибке)

**GPU VM конфигурация:**

| Param | Value |
|---|---|
| Flavor | `c5293c19-...` (RTX 4090, 12vCPU, 120GB RAM) |
| Image | Ubuntu 24.04 LTS + GPU Driver 580 Open |
| Network | ru-7 private (`192.168.0.0/24`) |
| Keypair | `OpenClaw` |

### GitHub Secrets (репо nkz-soft/expedition-ds-scaning)

| Secret | Value |
|---|---|
| `SELECTEL_USER` | `openclaw` |
| `SELECTEL_PASSWORD` | *(в infra repo secrets)* |
| `SELECTEL_ACCOUNT_ID` | `217113` |
| `SELECTEL_PROJECT_ID` | `187be2a17337471db67388ce0bf49e85` |
| `MINIO_ROOT_USER` | `minio_admin` |
| `MINIO_ROOT_PASSWORD` | *(спросить у Afflictus)* |

### Запустить обучение вручную

```bash
# Тегом:
git tag v0.1.0 && git push origin v0.1.0

# Или через GitHub UI:
# Actions → Train Model → Run workflow
```

---

## Dataset (Selectel S3)

Обучающая выборка (~133 GB):

```
Endpoint:   s3.ru-7.storage.selcloud.ru:443
Bucket:     train-expds-2
Access Key: a064df53e320474396c1de1c82dd858e
Secret Key: b1f66191dfe34927992afe3cc62a66ce
```

Локально на VM: `/opt/datasets/train/`

GPU VM монтирует датасет по NFS с main VM (read-only):
```
192.168.0.239:/opt/datasets  →  /opt/datasets  (монтируется в cloud-init)
```

### Ручная синхронизация

```bash
mc alias set expds https://s3.ru-7.storage.selcloud.ru \
  a064df53e320474396c1de1c82dd858e \
  b1f66191dfe34927992afe3cc62a66ce

mc mirror --overwrite --retry --summary --quiet expds/train-expds-2 /opt/datasets/train/
```

### Автоматическая синхронизация (systemd timer)

Настроен systemd timer на main VM — синк каждый день в 03:00 UTC (07:00 Саратов).

```bash
# Статус
systemctl status s3-dataset-sync.timer
systemctl status s3-dataset-sync.service

# Запустить вручную (не ждать расписания)
systemctl start s3-dataset-sync.service

# Посмотреть лог
tail -f /var/log/s3-dataset-sync.log

# Следующий запуск
systemctl list-timers s3-dataset-sync.timer
```

Файлы:
- `/etc/systemd/system/s3-dataset-sync.service`
- `/etc/systemd/system/s3-dataset-sync.timer`

### Проверить что обновилось

```bash
# Файлы изменённые за последний час
find /opt/datasets/train/ -mmin -60 -type f | sort
```

---

## Структура репо

```
ds-expedition-infra/
├── ansible/
│   ├── inventories/production/hosts.yml
│   ├── playbooks/
│   │   ├── base-setup.yml          # Базовая настройка VM
│   │   └── setup-github-runner.yml # Установка GitHub runner
│   └── roles/
│       ├── base-setup/
│       └── github-runner/
├── docker/
│   └── ml-stack/
│       ├── docker-compose.yml
│       └── mlflow.Dockerfile
├── scripts/
│   ├── selectel_vm.py      # CLI для управления GPU VM
│   └── cloud-init-gpu.yaml # Инициализация GPU VM
└── .github/
    └── workflows/
        └── train.yml       # Workflow для обучения (копия)
```
