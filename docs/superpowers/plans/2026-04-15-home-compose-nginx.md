# 家裡工作站 Docker Compose + Nginx 單一入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 Docker Compose 加入 **Nginx** 服務，對外只開 **一個主機埠**（預設 **`HTTP_PORT=8080`** 對應到容器內 80，可覆寫），提供前端 production 靜態檔並將 **`/api/`** 反代至內網 **backend**；**backend** 與 **triposr-api** 不對主機發布埠；**CORS** 預設涵蓋 `http://127.0.0.1:8080` 與 `http://localhost:8080`（見附錄 **Grill-me 定案**）。

**Architecture:** 三容器拓樸不變：**triposr-api**（GPU）← **backend** ← 瀏覽器經 **nginx** 同源 `/api`。前端沿用相對路徑 `/api/...`，由 Nginx `proxy_pass` 轉發至 `http://backend:8000/api/...`。**backend** 增加 **healthcheck**，**nginx** `depends_on` 等待 **backend** healthy。

**Tech Stack:** Docker Compose v2、`compose.yaml`、官方 **nginx** 映像（Alpine）、**Node** 多階段建置 **Vite** `frontend`、既有 **FastAPI**／**triposr-api** 映像。

**設計依據：** `docs/superpowers/specs/2026-04-15-home-docker-nginx-design.md`

---

## 檔案／責任對照（實作前先鎖定邊界）

| 路徑 | 動作 | 責任 |
|------|------|------|
| `nginx/Dockerfile` | 新建 | Node 建 `frontend/dist` → Nginx 最終映像 |
| `nginx/default.conf` | 新建 | 靜態 SPA、`/api/` 反代、`client_max_body_size`、逾時 |
| `.dockerignore`（repo 根目錄） | 新建 | 縮小 build context（含 `backend/storage` 等，見 Task 2） |
| `.gitignore`（repo 根目錄） | 修改 | 忽略 `compose.override.yaml`（見 Task 2） |
| `compose.yaml` | 修改 | 新增 `nginx`、backend 健康檢查、拿掉 backend 對外埠、CORS／`HTTP_PORT` 預設（8080）、nginx 依賴 |
| `README.md` | 修改 | 「一鍵起服務」：前置條件、WSL 注意、`compose.override`、環境變數、curl、驗收 |
| `docs/superpowers/specs/2026-04-15-home-docker-nginx-design.md` | 修改 | 與 Grill-me 定案對齊（預設埠、CORS、附錄修訂說明） |

---

### Task 1: 在 README 記錄 TripoSR 建置目錄（與現有 `additional_contexts` 一致）

**Files:**

- Modify: `README.md`（在「Local Implementation」或新小節 **「Docker Compose 部署（家裡工作站）」** 開頭插入）

**內容（整段貼上；可依 README 語系微調標題，勿刪既有附錄意義）：**

```markdown
### Docker Compose 部署（家裡工作站）

**TripoSR 原始碼路徑（建置必要）：** `compose.yaml` 內 `triposr-api` 使用 `additional_contexts.triposr-main: ../TripoSR-main`，意即 **與本 repo 同層** 須存在目錄 `TripoSR-main/`（內容為 TripoSR 專案根）。若你的 TripoSR 放在其他路徑，請在執行 `docker compose build` 前改寫該行，或於本機建立符號連結對齊 `../TripoSR-main`。

**主機需求：** 安裝 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)，且 GPU 驅動版本須能執行映像內 CUDA 12.6 PyTorch（與 `services/triposr-api/Dockerfile` 一致）。

**Windows／WSL：** 若以 Windows 為主，建議在 **WSL2 的 Linux 檔案系統** 內將本 repo 與 `TripoSR-main` **同層放置**後再執行 `docker compose build`，避免 Windows 路徑與 Docker build context 不一致。

**本機覆寫：** 可在 repo 根目錄自建 `compose.override.yaml` 覆寫服務設定；該檔名已列入 `.gitignore`，不會進版控。
```

- [ ] **Step 1:** 將上段插入 `README.md` 適當位置（建議在現有 TripoSR 小節附近，使「本機 conda」與「Compose」並列可找）。

- [ ] **Step 2:** Commit

```bash
git add README.md
git commit -m "docs: document TripoSR sibling path for Compose builds"
```

---

### Task 2: 新增 repo 根目錄 `.dockerignore` 並更新 `.gitignore`

**Files:**

- Create: `.dockerignore`
- Modify: `.gitignore`

**`.dockerignore` 完整內容（四行）：**

```gitignore
.git
frontend/node_modules
frontend/dist
backend/storage
```

**`.gitignore`：** 在檔案末尾新增一行（若已存在則略過）：

```gitignore
compose.override.yaml
```

- [ ] **Step 1:** 建立 `.dockerignore`，內容與上列完全一致。

- [ ] **Step 2:** 於 `.gitignore` 加入 `compose.override.yaml`。

- [ ] **Step 3:** Commit

```bash
git add .dockerignore .gitignore
git commit -m "chore: add root .dockerignore and ignore compose overrides"
```

---

### Task 3: 新增 `nginx/default.conf`

**Files:**

- Create: `nginx/default.conf`

**完整檔案內容：**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # 後端允許 10MB；略放大邊界與 multipart 開銷
    client_max_body_size 15m;

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 120s;
    }

    location = /health {
        proxy_pass http://backend:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 1:** 建立 `nginx/default.conf`，內容與上列完全一致。

- [ ] **Step 2:** Commit

```bash
git add nginx/default.conf
git commit -m "feat(deploy): add nginx site config for SPA and API proxy"
```

---

### Task 4: 新增 `nginx/Dockerfile`（multi-stage）

**Files:**

- Create: `nginx/Dockerfile`

**完整檔案內容：**

```dockerfile
# syntax=docker/dockerfile:1

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.26-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /src/dist /usr/share/nginx/html
```

- [ ] **Step 1:** 建立 `nginx/Dockerfile`，內容與上列完全一致（`compose` build context 為 repo 根目錄時，`COPY frontend/` 路徑正確）。

- [ ] **Step 2:** 本機驗證僅建 nginx 映像（**不**需 GPU；可略過若無 Docker）

```bash
docker build -f nginx/Dockerfile -t life-course-nginx:test .
```

預期：最後一行類似 `Successfully tagged life-course-nginx:test`。

- [ ] **Step 3:** Commit

```bash
git add nginx/Dockerfile
git commit -m "feat(deploy): add multi-stage nginx image with Vite build"
```

---

### Task 5: 修改 `compose.yaml`（nginx、backend 健康檢查、埠、CORS）

**Files:**

- Modify: `compose.yaml`

**替換方針（整檔應與下列語意一致；若你檔內已有其他服務勿刪，僅合併變更）：**

1. **`backend` 區塊**
   - **移除** `ports: - "8000:8000"`（符合 spec：不對主機發布）。
   - **`environment.CORS_ALLOWED_ORIGINS`** 改為：

```yaml
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS:-http://127.0.0.1:8080,http://localhost:8080}
```

   - **新增** `healthcheck`（使用映像內建 `python`，無須改 `backend/Dockerfile`）：

```yaml
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "python -c \"import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5); assert r.status == 200; r.read()\"",
        ]
      interval: 10s
      timeout: 8s
      retries: 5
      start_period: 30s
```

2. **新增頂層 `nginx` 服務**（與 `backend`、`triposr-api` 同層 `services:`）：

```yaml
  nginx:
    build:
      context: .
      dockerfile: nginx/Dockerfile
    ports:
      - "${HTTP_PORT:-8080}:80"
    depends_on:
      backend:
        condition: service_healthy
```

- [ ] **Step 1:** 依上列修改 `compose.yaml`。

- [ ] **Step 2:** 驗證 Compose 語法

```bash
docker compose config >/tmp/compose.out && head -n 5 /tmp/compose.out
```

預期：無錯誤訊息，且 `/tmp/compose.out` 含 `nginx:`、`backend:`、`triposr-api:`。

- [ ] **Step 3:** Commit

```bash
git add compose.yaml
git commit -m "feat(deploy): add nginx service and internal-only backend"
```

---

### Task 6: README — 操作指令、環境變數、curl 驗收

**Files:**

- Modify: `README.md`（延續 Task 1 小節；**勿**使用巢狀 fenced code，下列每一段在 README 中為獨立標題／表格／程式碼區塊。）

**在「Docker Compose 部署（家裡工作站）」小節內依序追加：**

**段落 A — 標題與段落 `**啟動（專案根目錄）：**` 後接 bash 區塊：**

```bash
docker compose build
docker compose up
```

**段落 B — 標題 `**環境變數（選用）：**` 後接表格（照抄儲存格）：**

| 變數 | 預設 | 說明 |
|------|------|------|
| `HTTP_PORT` | `8080` | 對外 HTTP 埠（主機埠 → 容器 nginx **80**） |
| `CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:8080,http://localhost:8080` | 逗號分隔；若改 `HTTP_PORT` 須一併調整來源埠。若以區網 IP 開網頁，請加上 `http://<你的區網IP>:<HTTP_PORT>`。若要以本機 **Vite 5173** 直連 `backend` 除錯，請自行追加 `http://127.0.0.1:5173,http://localhost:5173`（需暫時對外打開 backend 埠時請用 `compose.override.yaml`）。 |

**段落 C — 標題 `**驗收（主機上，Compose 已 up）：**` 後接第一段 curl：**

```bash
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:${HTTP_PORT:-8080}/
```

接一行說明：預期輸出 `200`。

**段落 D — 第二段 curl：**

```bash
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:${HTTP_PORT:-8080}/health
```

接一行說明：預期輸出 `200`（JSON 內 `triposr_ok` 是否為 true 依 GPU／服務狀態而定，但 HTTP 應為 200）。

**段落 E — 結尾一句：** 瀏覽器開 `http://127.0.0.1:8080`（或 `http://localhost:8080`，若已改 `HTTP_PORT` 則替換埠號）應載入前端；上傳圖片跑完整流程須 GPU 與 triposr-api healthy。

- [ ] **Step 1:** 將段落 A～E 寫入 `README.md`（順序與上相同；程式碼區塊各自獨立，中間不包外層 fence）。

- [ ] **Step 2:** Commit

```bash
git add README.md
git commit -m "docs: document compose up, env vars, and curl checks for nginx entry"
```

---

### Task 7: 手動整線驗收（需 NVIDIA + TripoSR 目錄）

**Files:**

- 無（僅命令）

- [ ] **Step 1:** 確認 `../TripoSR-main` 存在且含 TripoSR 原始碼。

- [ ] **Step 2:**

```bash
docker compose build && docker compose up -d
```

預期：`docker compose ps` 顯示 `nginx`、`backend`、`triposr-api` 皆 `running`（`triposr-api` 首次可能 `health: starting` 直至 healthy）。

- [ ] **Step 3:** 重跑 Task 6 的 curl；瀏覽器驗證上傳流程。

- [ ] **Step 4:** 確認主機 **無須**開 `http://127.0.0.1:8000` 仍可完成流程（8000 未發布時應連線失敗，屬預期）。

- [ ] **Step 5:** 若全數通過，可打標籤或開 PR；無強制 commit。

---

## Spec 對照自檢（計畫撰寫者已完成）

| Spec 段落 | 對應任務 |
|-----------|----------|
| 單一對外埠（預設 8080→容器 80）、可覆寫 | Task 5 `HTTP_PORT`、Task 6 文件、修 spec |
| nginx 靜態 + `/api/` 反代 | Task 3、4、5 |
| backend／triposr-api 不對外發布 | Task 5 移除 backend `ports` |
| CORS 本機 + 可擴區網 | Task 5、Task 6 |
| TripoSR 目錄文件化 | Task 1、Task 7 |
| 驗收 curl + 瀏覽器 | Task 6、Task 7 |
| SPA `try_files` | Task 3 |
| 上傳大小 | Task 3 `client_max_body_size` |
| 依賴順序（nginx 等 backend） | Task 5 `depends_on` + backend `healthcheck` |
| 非目標 HTTPS／K8s | 無任務 |

**占位符掃描：** 無 TBD／TODO 步驟。

---

## 計畫完成後的執行方式

計畫已存於 `docs/superpowers/plans/2026-04-15-home-compose-nginx.md`。實作時可擇一：

**1. Subagent-Driven（建議）** — 每個 Task 派新 subagent，任務間由你審閱；需使用 **superpowers:subagent-driven-development**。

**2. Inline Execution** — 在本對話依序執行 Task，搭配檢查點批次跑；需使用 **superpowers:executing-plans**。

請告訴我要用 **1** 還是 **2**。

---

## Grill-me 定案（2026-04-15）

以下為 `/grill-me` 對本計畫之收斂；實作與 **spec** 修訂以此為準。若與上文任務內 YAML／表格衝突，以本表為準。

| 題次 | 議題 | 定案 |
|------|------|------|
| 1 | 對外 HTTP 預設埠 | 主機預設 **`HTTP_PORT=8080`**，對應容器內 nginx **listen 80**（`ports: "${HTTP_PORT:-8080}:80"`）。若需無埠號網址，可自行設 `HTTP_PORT=80` 並處理主機權限。 |
| 2 | `CORS_ALLOWED_ORIGINS` 預設 | `http://127.0.0.1:8080,http://localhost:8080`；本機 Vite **5173** 直連除錯時由開發者自行追加對應 origin。 |
| 3 | 根目錄 `.dockerignore` | 含 **`backend/storage`**，避免本機上傳測試產物膨脹 build context。 |
| 4 | Nginx 是否轉發 **`GET /health`** | **保留**（家裡／辦公室除錯便利）；勿將該埠無防護暴露於公網。 |
| 5 | 設計 spec 是否同步 | **同步修訂** `docs/superpowers/specs/2026-04-15-home-docker-nginx-design.md`（預設埠、CORS 範例、驗收敘述），並可加一小節「修訂紀錄」指向本表。 |
| 6 | `compose.override.yaml` | 列入根 **`.gitignore`**；README **一句**說明可自建覆寫且不進版控。 |
| 7 | Windows／WSL | README **簡短注意**：建議 WSL2 Linux 檔案系統內同層放置 repo 與 `TripoSR-main` 再 build。 |
| 8 | 決策可追溯性 | 於本計畫檔保留本附錄；PR 描述可指向本檔。 |
