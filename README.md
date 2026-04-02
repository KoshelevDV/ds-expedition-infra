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

## Self-hosted GitHub Runner

Runner `gpu-ml-01` зарегистрирован в репо `nkz-soft/expedition-ds-scaning`.

```yaml
# В workflow указывать:
runs-on: [self-hosted, linux, gpu-orchestrator]
```

Сервис: `actions.runner.nkz-soft-expedition-ds-scaning.gpu-ml-01`

```bash
# Статус
systemctl status 'actions.runner.*'

# Перезапуск
cd /opt/actions-runner && ./svc.sh stop && ./svc.sh start
```

Переустановка (если истёк токен):
```bash
cd /opt/projects/ds-expedition-infra
ansible-playbook \
  -i ansible/inventories/production/hosts.yml \
  ansible/playbooks/setup-github-runner.yml \
  -e "runner_token=<NEW_TOKEN>"
```

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
| Flavor | `GL10.8-65536-0-1GPU` (RTX 4090, 8vCPU, 64GB RAM) |
| Image | Ubuntu 22.04 + GPU Driver 590 + Docker |
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

Обучающая выборка (~132 GB):

```
Endpoint:   s3.ru-7.storage.selcloud.ru:443
Bucket:     train-expds-2
Access Key: a064df53e320474396c1de1c82dd858e
Secret Key: b1f66191dfe34927992afe3cc62a66ce
```

Скачать на VM:
```bash
mc alias set expds s3://s3.ru-7.storage.selcloud.ru \
  a064df53e320474396c1de1c82dd858e \
  b1f66191dfe34927992afe3cc62a66ce
mc mirror expds/train-expds-2 /opt/datasets/
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
