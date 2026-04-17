---

## title: Docker Compose 加入 Nginx 與前端靜態（家用 GPU 工作站）
type: feat
status: completed
date: 2026-04-15

# Docker Compose 加入 Nginx 與前端靜態（家用 GPU 工作站）

## 權威來源與分工（對齊說明）

本檔為 repo `docs/plans/` 內之**追蹤用計畫**；**設計真實來源**與**逐步實作核銷清單**以另兩份為準，避免三處漂移：

| 文件 | 角色 |
|------|------|
| `docs/superpowers/specs/2026-04-15-home-docker-nginx-design.md` | 設計規格、驗收標準、非目標 |
| `docs/superpowers/plans/2026-04-15-home-compose-nginx.md` | 任務分解（Task 1–7）、檔案路徑、commit 建議、checkbox |

若本檔與上列任一文牴觸，**以上表順序為準**（先 spec，次 superpowers 計畫）。

## Overview

在既有 `compose.yaml`（`backend` + `triposr-api`、NVIDIA GPU）上新增 **Compose 服務 `nginx`**：對外僅 **一個主機埠**（預設 **`HTTP_PORT=8080` → 容器 80**），以 **multi-stage** 建置提供 `frontend` 的 production 靜態檔，並將 **`/api/`** 反代至內網 **`backend:8000`**，使瀏覽器維持與 `frontend/src/api.js` 一致之**同源** `fetch('/api/...')`（與 Vite dev 的 proxy 路徑語意對齊，但正式部署走 nginx）。

## Problem Frame

目標環境為 **自家／辦公室具 NVIDIA GPU 的工作站 + Docker**。目前完整 UI 仰賴本機 Vite；Compose 預設僅暴露後端相關服務，**缺少**「前端 + 單一 HTTP 入口」的一鍵路徑。

## Requirements Trace

- **R1.** `docker compose build` / `docker compose up`（或專案慣用指令）在具備 TripoSR 建置前置條件下可啟動 **nginx + backend + triposr-api**。
- **R2.** 瀏覽器自 **單一 origin**（預設 `http://127.0.0.1:8080` 或 `http://localhost:8080`）載入前端並成功呼叫 `POST /api/image-to-3d`（同源反代）。
- **R3.** `CORS_ALLOWED_ORIGINS` 與實際瀏覽器 Origin 對齊；預設值見下節 **Grill-me lock-in**；區網或自訂埠由 README／環境變數覆寫（見 superpowers 計畫 Task 5–6）。
- **R4.** Nginx `client_max_body_size` **不得低於**後端 `backend/app/validation.py` 之 `MAX_FILE_SIZE`（10 MiB）；實作範本採 **15m**（見 superpowers 計畫 `nginx/default.conf`）。
- **R5.** 反代逾時須涵蓋推論鏈路；實作採 **`proxy_read_timeout` / `proxy_send_timeout` 120s**（固定值，與 spec／superpowers 計畫一致）；若日後調高 `TRIPOSR_API_TIMEOUT_SECONDS`，應同步調整 Nginx 並更新文件。
- **R6.** `triposr-api` 之 `additional_contexts: ../TripoSR-main` **維持不變**；僅文件化前置目錄（superpowers Task 1、7）。

## Scope Boundaries

- 不含 Kubernetes、雲端託管、TLS 自動化（與 spec 非目標一致）。
- 不變更核心 API 契約（`/api/image-to-3d`、`/health`）；僅新增「如何從外部到達」。
- 不以 Playwright／E2E 為交付強制項；以 **curl**、`docker compose config`、手動瀏覽器流程為主（spec §9、superpowers Task 6–7）。
- 不更名 `compose.yaml`；本機覆寫使用 **`compose.override.yaml`**（列於 `.gitignore`，見 Grill-me）。

## Context & Research（摘要）

- `compose.yaml`：實作前可能仍有 `backend` 對外 `8000:8000`；目標為**移除**對外 mapping，改由 **nginx** 發布 `HTTP_PORT`。
- `frontend/vite.config.js`：僅 dev 代理；production 倚賴 nginx。
- `frontend/src/api.js`：相對路徑 `/api/...`。
- `backend/app/main.py`：`CORSMiddleware`、`POST /api/image-to-3d`、`/health`。
- `backend/app/validation.py`：`MAX_FILE_SIZE = 10 * 1024 * 1024`。
- 測試：`backend/tests/test_image_to_3d.py`（後端契約不變）。

## Key Technical Decisions（與 spec／superpowers 一致）

- **服務名稱 `nginx`**（非 `web`）；映像由 **`nginx/Dockerfile`**（repo 根為 build `context`）multi-stage 建置：`npm run build` → 最終 **`nginx:alpine`**，設定檔 **`nginx/default.conf`**。
- **對外埠**：`"${HTTP_PORT:-8080}:80"`；容器內 nginx **listen 80**。
- **backend** 不對主機發布埠；**triposr-api** 不對主機發布埠。
- **backend `healthcheck`** + **nginx `depends_on` … `condition: service_healthy`**（見 superpowers Task 5）。
- **根目錄 `.dockerignore`**：與 superpowers Task 2 四行一致（含 **`backend/storage`**）。
- **CORS** 預設字串與 Grill-me 表一致（見下節）。
- **`GET /health`**：經 nginx **保留**轉發至 backend（家裡／辦公室情境）；勿將對外埠暴露於無防護公網。
- **SPA**：`try_files $uri $uri/ /index.html;`。
- **gzip**：**未**列入目前 spec／superpowers 交付範本；若產品要強制啟用，須另開決策並同步三份文件與 `nginx/default.conf`。

## Grill-me lock-in（2026-04-15）

以下與 `docs/superpowers/specs/2026-04-15-home-docker-nginx-design.md` §11 及 `docs/superpowers/plans/2026-04-15-home-compose-nginx.md` 附錄**逐字對齊**；實作以此為準。

| 項目 | 定案摘要 |
|------|----------|
| 對外預設埠 | 主機 **8080** → 容器 nginx **80**（`HTTP_PORT`） |
| CORS 預設 | `http://127.0.0.1:8080`、`http://localhost:8080` |
| Build context | 根 `.dockerignore` 排除 **`backend/storage`** |
| `/health` | 經 nginx **保留**對外轉發（家裡／辦公室情境） |
| 本機覆寫 | **`compose.override.yaml`** 列入根 `.gitignore`；README 說明一句 |
| Windows | README 簡述 **WSL2** 同層放置 repo 與 `TripoSR-main` 之建議 |

（superpowers 計畫附錄另含「設計 spec 同步修訂」「決策可追溯性」等流程欄位，意義與本表一致。）

## Implementation Units（對照 superpowers Task 1–7）

| Unit | 對應 Task | 摘要 |
|------|-----------|------|
| 文件與前置條件 | Task 1 | README：`TripoSR-main` 同層、NVIDIA Toolkit、WSL、`compose.override` |
| `.dockerignore` / `.gitignore` | Task 2 | 四行 `.dockerignore`；忽略 `compose.override.yaml` |
| Nginx 設定 | Task 3 | 新建 `nginx/default.conf`（`/api/`、`/health`、SPA、`client_max_body_size`、逾時） |
| Nginx 映像 | Task 4 | 新建 `nginx/Dockerfile`（multi-stage） |
| Compose 連線 | Task 5 | `compose.yaml`：nginx 服務、backend healthcheck、移除 backend 對外埠、CORS／`HTTP_PORT` |
| README 操作面 | Task 6 | `compose up`、環境變數表、curl 驗收 |
| 整線驗收 | Task 7 | GPU 機上手動驗證 |

執行細節（含完整片段與 checkbox）請直接依 **`docs/superpowers/plans/2026-04-15-home-compose-nginx.md`** 逐項核銷。

## System-Wide Impact

- 瀏覽器僅面向 **nginx**；**nginx → backend → triposr-api**。
- 錯誤模型不因本次變更重做；Nginx 502/504 仍由前端既有邏輯呈現。
- TripoSR GPU、`./backend/storage` volume 等不變。

## Risks & Dependencies

與 spec §6、§9 及 superpowers 計畫「Spec 對照自檢」「Task 7」一致：TripoSR 目錄缺失、413 上傳限制、逾時、LAN CORS、埠占用（`HTTP_PORT`）等。

## Documentation / Operational Notes

- 以 **README** 為操作者主要入口（superpowers Task 1、6）；**不**將 `.env.example` 列為本對齊版本的強制交付項（與 superpowers 計畫一致）；若日後要統一引入 `.env.example`，應同步更新**三份**文件與 Task 清單。

## Sources & References

- **Design spec：** `docs/superpowers/specs/2026-04-15-home-docker-nginx-design.md`
- **Task plan：** `docs/superpowers/plans/2026-04-15-home-compose-nginx.md`
- Related code: `compose.yaml`, `frontend/vite.config.js`, `frontend/src/api.js`, `backend/app/main.py`, `backend/app/validation.py`
- Related tests: `backend/tests/test_image_to_3d.py`
