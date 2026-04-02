# ds-expedition-infra

Infrastructure for Expedition DS Scanning competition.

## VM

| Param | Value |
|---|---|
| Host | 212.74.224.231 |
| SSH port | 22022 |
| User | root / mlops |
| OS | Ubuntu 24.04 LTS |
| Key | `~/.ssh/selectel_ds_scan` |

```bash
ssh -i ~/.ssh/selectel_ds_scan -p 22022 root@212.74.224.231
```

## ML Stack (docker-compose)

| Service | Port | Description |
|---|---|---|
| MLflow | localhost:5000 | Experiment tracking |
| MinIO Console | localhost:9001 | S3 artifact storage UI |
| MinIO API | localhost:9000 | S3 endpoint (DVC remote) |
| JupyterLab | localhost:8888 | Development notebooks |

**Все порты только localhost** — доступ через SSH tunnel:

```bash
ssh -i ~/.ssh/selectel_ds_scan -p 22022 -L 5000:localhost:5000 -L 9001:localhost:9001 -L 8888:localhost:8888 root@212.74.224.231
```

### Управление

```bash
# Запуск
cd /opt/ml-stack && docker compose up -d

# Статус
docker compose ps

# Логи
docker compose logs mlflow
docker compose logs minio
```

### MinIO бакеты

| Bucket | Purpose |
|---|---|
| `mlflow-artifacts` | MLflow artifacts |
| `dvc-remote` | DVC data versioning |
| `datasets` | Competition dataset cache |
| `checkpoints` | Model checkpoints |
| `submissions` | GeoJSON submissions |

### rclone config (DVC remote)

```ini
[selectel-ml]
type = s3
provider = Minio
endpoint = http://localhost:9000
access_key_id = minio_admin
secret_access_key = <MINIO_ROOT_PASSWORD from .env>
```

## Ansible

```bash
# Базовая настройка VM
ansible-playbook ansible/playbooks/base-setup.yml \
  -i ansible/inventories/production/hosts.yml
```

## Directories on VM

```
/opt/projects/     ← git repos
/opt/datasets/     ← competition dataset (132 GB)
/opt/artifacts/
  checkpoints/     ← model weights
  submissions/     ← geojson submissions
  logs/            ← training logs
/opt/ml-stack/     ← docker-compose + .env
/opt/ml-env/       ← python venv (python3.12)
```
