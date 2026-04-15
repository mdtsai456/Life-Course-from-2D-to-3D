# 設計：家裡／辦公室工作站以 Docker Compose + Nginx 部署

**日期：** 2026-04-15  
**狀態：** 已與需求方對齊（腦力激盪核准）  
**範圍：** 單機、具 NVIDIA GPU、以 Docker 一鍵起服務；對外單一 HTTP 入口。

## 1. 目標與非目標

### 1.1 目標

- 使用 **Docker Compose** 同時運行 **Nginx（前端靜態 + API 反代）**、既有 **backend**、既有 **triposr-api**。
- 瀏覽器僅透過 **單一對外埠**（預設 **80**）使用應用；前端與 API 為 **同源**，避免不必要的 CORS 複雜度。
- 維持 **triposr-api** 需 **NVIDIA GPU**、**backend** 呼叫內部 `triposr-api` 的現有整合方式。

### 1.2 非目標（本規格不涵蓋）

- TLS／HTTPS、憑證與自動更新。
- 多機水平擴展、Kubernetes。
- 變更 TripoSR 演算法或模型權重取得方式（僅文件化建置前置條件）。

## 2. 架構與服務邊界

| 服務 | 對主機網路 | 職責 |
|------|------------|------|
| **nginx** | **發布** 例如 `0.0.0.0:80->80` | 提供前端 production 靜態檔；將 **`/api/`** 反向代理至 `backend:8000`。 |
| **backend** | **不發布**（僅 Compose 內部） | 既有 FastAPI；環境變數 `TRIPOSR_API_URL` 指向 `http://triposr-api:8001`；檔案儲存於 `STORAGE_ROOT`。 |
| **triposr-api** | **不發布**（僅 Compose 內部） | 既有 TripoSR 推論服務；需 GPU；保留 **healthcheck**。 |

### 2.1 瀏覽器資料流

1. `GET /` 與靜態資源：由 **nginx** 直接提供（來自建置階段產出之 `dist`）。
2. `POST /api/...`（含現有 `fetch('/api/image-to-3d', …)`）：瀏覽器打到同源 **nginx**，再由 **proxy_pass** 轉發至 **backend**，路徑前綴與現有 FastAPI 路由一致。

### 2.2 服務依賴順序

- **backend** 須在 **triposr-api** 健康後才可視為就緒（與現有 `depends_on` + `condition: service_healthy` 一致）。
- **nginx** 須在 **backend** 可連線後提供 `/api` 反代；建議以 **`depends_on`**（必要時搭配簡易啟動重試或 healthcheck）避免 nginx 先起而反代失敗。

## 3. Nginx 與前端建置

### 3.1 映像建置策略

採 **multi-stage Dockerfile**（或等效：一階段 Node 建 `frontend`，最終階段 **nginx** 映像只含 `dist` 與設定檔），以確保 production 資產可重現、映像不含完整 Node dev 依賴。

### 3.2 Nginx 行為需求

- **`location /api/`**：反向代理至 `http://backend:8000`，**proxy_pass 與尾隻斜線寫法**須與 FastAPI 註冊路徑一次對齊，避免雙斜線或截斷前綴。
- **SPA**：靜態根目錄服務 `index.html`；對非實體檔案路徑之導覽應回退至 `index.html`，避免重新整理 404。

### 3.3 與現有前端的對齊

- 現有 `frontend/src/api.js` 使用 **相對路徑** `/api/...`，在「同源 + Nginx 反代」下 **無須**為部署改為絕對後端網址。

## 4. Compose 與網路埠

- **僅 nginx** 對主機 **publish** 預設 **80**（埠號可透過 compose 變數覆寫，本規格以 80 為預設文件值）。
- **backend** 與 **triposr-api** 的 **8000／8001 不對主機發布**（降低誤連與暴露面）；除錯若需直連 backend，屬開發者本機臨時調整，非本規格預設交付形態。

## 5. 環境變數與 CORS

- **backend** 之 `CORS_ALLOWED_ORIGINS` 應包含使用者實際入口，例如 `http://127.0.0.1`、`http://localhost`，以及以區網 IP 存取時之 `http://<區網IP>`（建議以 **單一環境變數** 或 compose 檔內明列方式設定，避免過寬 `*`）。
- 同源經 nginx 時，多數請求不觸發 CORS；仍保留正確 CORS 設定，以支援未來可能的前後端分離或開發模式。

## 6. TripoSR 原始碼建置前置條件

- 現有 **triposr-api** 映像建置使用 **`additional_contexts`** 引入 **`../TripoSR-main`**（相對於 repo 根目錄之兄弟目錄）。**實作計畫**須明列：建置機器上目錄配置或改為 submodule／內嵌目錄之擇一方案；本設計規格僅要求「文件與指令可重現」，不在此處預先指定唯一檔案布局，以免與既有 Dockerfile 未同步之實作衝突。

## 7. 儲存與持久化

- 維持 **backend** 將 `./backend/storage`（或等效 named volume）掛載至容器內 `STORAGE_ROOT`，與是否引入 nginx **無關**。

## 8. 驗收標準（家裡工作站）

1. 於具 NVIDIA Container Toolkit 與符合既有映像需求之機器上，依文件完成建置前置條件後，執行 **`docker compose up`**（或專案慣用指令）可啟動三服務且 **nginx 對外 80** 可連線。
2. 瀏覽器僅使用 **`http://<主機>:80`** 可完成上傳影像並取得 3D 結果之完整流程。
3. 預設配置下，主機上 **不可**（或不必）依賴 `http://<主機>:8000` 對外提供服務即可完成上述流程。

## 9. 測試與品質（實作計畫應涵蓋）

- 靜態與反代：至少以 **curl** 驗證 `GET /` 回 200、`GET` 或 **OPTIONS** 對關鍵 `/api` 路徑行為符合預期（細節由實作計畫訂定）。
- 若專案已有整合測試，應評估是否在 CI 以 **無 GPU** 之 mock 或僅建 nginx/backend 映像層驗證建置可通過；**full stack 含 GPU** 以本機／手動驗收為主。

## 10. 後續流程

- 經需求方確認本文件無誤後，以 **writing-plans** 產出實作計畫（檔案路徑與命名依該技能與 repo 慣例）。
