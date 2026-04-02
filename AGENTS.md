# AGENTS.md — ds-expedition-infra

## What is this
Infrastructure repo for **Expedition DS. Scanning** competition (MLOps + GPU training pipeline).

## Stack
- **VM:** Ubuntu 24.04, Selectel ru-7b, `212.74.224.231` / private `192.168.0.239`
- **ML Stack:** Docker Compose — MLflow + MinIO + PostgreSQL + JupyterLab
- **Runner:** GitHub Actions self-hosted (`gpu-ml-01`, tags: `self-hosted,linux,gpu-orchestrator`)
- **Infra scripts:** Python (selectel_vm.py), Ansible, cloud-init
- **GPU VM:** Selectel GL10 (RTX 4090), image Ubuntu 22.04 + GPU Driver 590 + Docker, AZ ru-7b

## Structure
```
ansible/               — Ansible playbooks и роли
  inventories/         — hosts.yml (production)
  playbooks/           — base-setup.yml, setup-github-runner.yml
  roles/               — base-setup, github-runner
docker/ml-stack/       — docker-compose.yml + mlflow.Dockerfile
scripts/
  selectel_vm.py       — CLI: create/wait/ip/delete GPU VM через Selectel API
  cloud-init-gpu.yaml  — Инициализация GPU VM (Python 3.11, mc, зависимости)
.github/workflows/
  train.yml            — Workflow обучения (копия для истории, оригинал у Ника)
```

## Development Rules
- Все изменения инфраструктуры — коммитить сюда
- Workflow `train.yml` хранится здесь как эталон, Ник переносит руками в свой репо
- Secrets хранятся в GitHub Secrets обоих репо (не в коде!)
- `selectel_vm.py` использует env vars: `SELECTEL_USER`, `SELECTEL_PASSWORD`, `SELECTEL_ACCOUNT_ID`, `SELECTEL_PROJECT_ID`, `AVAILABILITY_ZONE`
- Изменения compose на VM применять через `docker compose up -d` в `/opt/ml-stack/`
- Синкать compose с репо после изменений на VM

## Status
- ✅ VM настроена (mlops юзер, SSH 22022, UFW, fail2ban, Docker)
- ✅ ML Stack запущен (MLflow :5000, MinIO :9000/:9001, Jupyter :8888)
- ✅ MLflow/MinIO слушают на private IP `192.168.0.239` (доступно GPU VM)
- ✅ Self-hosted runner зарегистрирован в `nkz-soft/expedition-ds-scaning`
- ✅ Selectel API авторизация работает (svc user `openclaw`)
- ✅ Train workflow написан (GPU flavor GL10 = RTX 4090, AZ ru-7b)
- ⏳ DVC remote — настроить в проекте Ника (заменит прямой mc mirror)
- ⏳ Flavor RTX 4090 проверить через `workflow_dispatch` перед реальным обучением

## How to run locally
```bash
# Подключиться к VM
ssh -i ~/.ssh/selectel_ds_scan -p 22022 root@212.74.224.231

# SSH tunnel для UI
ssh -i ~/.ssh/selectel_ds_scan -p 22022 \
  -L 5000:localhost:5000 -L 9001:localhost:9001 -L 8888:localhost:8888 \
  root@212.74.224.231

# Переустановить runner (нужен новый токен от Ника)
ansible-playbook -i ansible/inventories/production/hosts.yml \
  ansible/playbooks/setup-github-runner.yml \
  -e "runner_token=<TOKEN>"

# Тестовый запуск GPU VM через API
SELECTEL_USER=openclaw SELECTEL_PASSWORD=... \
  python3 scripts/selectel_vm.py create --name test --flavor 3102 \
  --image 01179c74-2d9e-4b59-8b93-c6a2b55d00ba \
  --key OpenClaw --network d0df791e-6044-46d1-a705-a7963beafb34
```

## Pitfalls
- **SSH socket на Ubuntu 24.04:** systemd override обязателен для смены порта (`/etc/systemd/system/ssh.socket.d/override.conf`)
- **Selectel project-scoped токен:** передавать `project.id`, не `project.name` (кириллица ломает JSON в shell)
- **GPU регион:** флейворы GL10 (RTX 4090) только в `ru-7`, AZ `ru-7b` совпадает с main VM
- **user_data в OpenStack:** должен быть base64-encoded (selectel_vm.py делает сам)
- **MLflow образ:** не устанавливать psycopg2/boto3 в entrypoint — использовать mlflow.Dockerfile
- **DVC:** TODO — Ник настраивает, пока артефакты через mc mirror в MinIO
