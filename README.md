# Life Course: Image-to-3D

> **完整 Web（瀏覽器上傳圖 → 3D）：** 請見 **[§3.3 Docker Compose 部署（家裡工作站）](#docker-compose-web)** — 內含 `cd` 到專案根目錄、`docker compose build`／`up`（含前景與 `-d` 背景）、預設 **[http://127.0.0.1:8080](http://127.0.0.1:8080)**，以及 `ps`／`logs`／`down` 等常用指令。

## 1. Task Description

單張影像輸入，產出 **Unity 可直接依下表驗收** 的 Ready 3D（有網格、UV、材質／貼圖正確）。

### 1.1 Input Single Image


| 項目  | 規格                                                  |
| --- | --------------------------------------------------- |
| 影像  | 單張 `.png` / `.jpg` / `.webp`（物件去背建議 `.png` 含 alpha） |


### 1.2 Output（可接受產出）

交付須一次給齊網格與貼圖（單檔或同目錄可引用）。匯入 Unity 後須 **Model + Materials 可對應、外觀與貼圖正確**，無須手動重建模型或重展 UV。非下表格式、或僅點雲／無貼圖 `.stl`／僅 2D 與影片／灰模無反照貼圖者，不採用。


| 優先  | 可接受產出                                   | Unity                     |
| --- | --------------------------------------- | ------------------------- |
| 1   | `.fbx` + 貼圖（`.png` / `.jpg` / `.tga` 等） | Model + Materials，貼圖路徑可還原 |
| 2   | `.glb`                                  | 單檔；專案須具 glTF 匯入           |
| 3   | `.gltf` + 貼圖                            | 同 `.glb`，檔案拆開             |
| 4   | `.obj` + `.mtl` + 貼圖                    | 備援                        |


## 2. Model Selection

### 2.1 2D->3D Model Candidates


| Model                   | Input                   | Output                                                 | GPU（Inference） |
| ----------------------- | ----------------------- | ------------------------------------------------------ | -------------- |
| InstantMesh（TencentARC） | `.png`, `.jpg`, `.webp` | `.obj`（vertex colors）；可 `.obj` + `.mtl` + 貼圖（如 `.png`） | 12GB–16GB      |
| TripoSR                 | `.png`, `.jpg`, `.webp` | `.obj`、`.glb`；可另產 `.png`（baked texture）                | 6GB–8GB        |
| Unique3D                | `.png`（建議去背／alpha）      | `.glb`（textured mesh）                                  | 16GB–24GB      |
| LRM／OpenLRM 等實作         | `.png`, `.jpg`, `.webp` | `.ply`（vertex colors；OpenLRM 推論 mesh）                  | 依權重 10GB–24GB  |


### 2.2 模型／權重放置建議


| 類型               | 建議路徑                                         | 備註                       |
| ---------------- | -------------------------------------------- | ------------------------ |
| 第三方程式（如 TripoSR） | `third_party/` 或 `external/`（專案根目錄）          | 由 `backend` 整合           |
| 權重（checkpoint）   | 預設：Hugging Face 快取；自訂：`backend/models/<名稱>/` | 大檔不入 git，`.gitignore` 排除 |
| 前端 `frontend/`   | —                                            | 不放推理模型                   |


## 3. Local Implementation for TripoSR

### 3.1 Environment Setup Summary

> *details at Appendix A.*

1. Create Virtual Environment
  ```bash
    conda create -n triposr python=3.10 -y
    conda activate triposr
  ```
2. Download cuda toolkit 12.6 (if not v12.6)
3. Install Dependencies
  ```bash
    pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
    pip install -r requirements.txt
    pip install onnxruntime-gpu
    pip install gradio --upgrade        # run if using gradio
    pip install transformers --upgrade  # run as facing Problem4
  ```

### 3.2 Inference

> *Remember to enter virtual environment `conda activate triposr`*

```bash
# 1. Manual Inference
python run.py examples/chair.png --output-dir output/`
python run.py examples/images2.jpg --output-dir output/test --model-save-format glb

# 2. Local Gradio App
python gradio_app.py
# * Running on local URL:  http://127.0.0.1:7860
```

- `--model-save-format {obj,glb}`: Format to save the extracted mesh. Default: 'obj'
- `--output-dir OUTPUT_DIR`: save mesh.glb (or .obj) and input.png at `[OUTPUT_DIR]/0/`

use command `python run.py --help` to see detail usage.

<a id="docker-compose-web"></a>

### 3.3 Docker Compose 部署（家裡工作站）

**TripoSR 原始碼路徑（建置必要）：** `compose.yaml` 內 `triposr-api` 使用 `additional_contexts.triposr-main: ../TripoSR-main`，意即 **與本 repo 同層** 須存在目錄 `TripoSR-main/`（內容為 TripoSR 專案根）。若你的 TripoSR 放在其他路徑，請在執行 `docker compose build` 前改寫該行，或於本機建立符號連結對齊 `../TripoSR-main`。

**主機需求：** 安裝 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)，且 GPU 驅動版本須能執行映像內 CUDA 12.6 PyTorch（與 `services/triposr-api/Dockerfile` 一致）。

**Windows／WSL：** 若以 Windows 為主，建議在 **WSL2 的 Linux 檔案系統** 內將本 repo 與 `TripoSR-main` **同層放置**後再執行 `docker compose build`，避免 Windows 路徑與 Docker build context 不一致。

**本機覆寫：** 可在 repo 根目錄自建 `compose.override.yaml` 覆寫服務設定；該檔名已列入 `.gitignore`，不會進版控。

**怎麼啟動（給第一次用的人）：**

1. **先進到專案根目錄**（與本 repo 的 `compose.yaml` 同一層）。在終端機把路徑換成你電腦上的位置，例如：
  ```bash
   cd /path/to/life-course-from-2d-to-3d
  ```
2. **建置 Docker 映像**（第一次 clone 後必做；`Dockerfile` 或依賴有變時也要重做；會花一段時間是正常的）：
  ```bash
   docker compose build
  ```
3. **啟動服務**（會一併啟動 `triposr-api`、`backend`、`nginx`）：
  - **前景模式**（終端機會一直顯示 log，適合除錯；要停就按 **Ctrl+C**）：
    ```bash
    docker compose up
    ```
  - **背景模式**（關掉終端機後服務仍繼續跑）：
    ```bash
    docker compose up -d
    ```
4. **用瀏覽器開網頁**：預設網址為 **[http://127.0.0.1:8080](http://127.0.0.1:8080)** 或 **[http://localhost:8080](http://localhost:8080)**（若你改了埠，請把 `8080` 換成環境變數 `HTTP_PORT` 的值）。
5. **常用指令**（背景啟動時特別有用）：
  ```bash
   docker compose ps          # 看三個服務是否 running / healthy
   docker compose logs -f     # 持續看 log（結束請 Ctrl+C）
   docker compose down        # 關掉並移除本次起的容器
  ```

<a id="docker-compose-restart"></a>

#### 容器自動重啟（restart 策略）

`compose.yaml` 內 `backend`、`nginx`、`triposr-api` 皆為 `restart: unless-stopped`：容器若**非正常結束**（例如程序崩潰），Docker 會自動再起；在 Docker daemon 或主機重啟後，亦有助於服務回到線上。

- **程序崩潰或被終止**：容器退出後，Docker 會依 restart 設定**自動再起**（前提是映像與設定可再次成功啟動）。
- **`docker compose stop`（只停不移除）**：屬於刻意停止；即使之後 Docker daemon 或主機重啟，這類先前已停止的容器**預設不會**因 restart 政策而自動回到 running（需再 `docker compose start` 或 `up`）。
- **`docker compose down`**：會**移除容器**；要恢復服務須再執行 `docker compose up`（`-d` 與否皆可）。

若某服務**啟動即退出**並在短時間內**反覆重啟**，請先 `docker compose logs -f <服務名>`（或 `docker compose logs -f`）查看錯誤；多為環境變數、GPU／驅動、`TripoSR-main` 路徑或依賴未就緒，而非無故「鬼打牆」。

**環境變數（選用）：**


| 變數                     | 預設                                            | 說明                                                                                                                                                                                                                |
| ---------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HTTP_PORT`            | `8080`                                        | 對外 HTTP 埠（主機埠 → 容器 nginx **80**）                                                                                                                                                                                  |
| `CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:8080,http://localhost:8080` | 逗號分隔；若改 `HTTP_PORT` 須一併調整來源埠。若以區網 IP 開網頁，請加上 `http://<你的區網IP>:<HTTP_PORT>`。若要以本機 **Vite 5173** 直連 `backend` 除錯，請自行追加 `http://127.0.0.1:5173,http://localhost:5173`（需暫時對外打開 backend 埠時請用 `compose.override.yaml`）。 |


**驗收（主機上，Compose 已 up）：**

```bash
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:${HTTP_PORT:-8080}/
```

預期輸出 `200`。

```bash
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:${HTTP_PORT:-8080}/health
```

預期：TripoSR 就緒時 HTTP `200`；未就緒或無法連線下游時 HTTP `503`（JSON 仍含 `status`、`triposr_ok`、`detail`）。僅需確認 backend 行程存活請打 `GET /health/live`（恒為 200）。

瀏覽器開 `http://127.0.0.1:8080`（或 `http://localhost:8080`，若已改 `HTTP_PORT` 則替換埠號）應載入前端；上傳圖片跑完整流程須 GPU 與 triposr-api healthy。

**`triposr-api`（Compose 內部）：** `docker compose` 將服務標為 **healthy** 時會打容器內 **`GET /health/ready`**（就緒 **200**、未就緒 **503**；JSON 欄位與 **`GET /health`** 一致）。除錯 sidecar 仍可用 **`GET /health`**（HTTP 恒 **200**，請看 JSON 的 `triposr_ok`）。

---

## Appendix A. Environment Setup Details / Troubleshooting

1. create virtual environment
  ```bash
    conda create -n triposr python=3.10 -y
    conda activate triposr
  ```
2. download cuda toolkit 12.6

- `where nvcc` to check existing cuda toolkit first.
- Go to Nvidia to find cuda toolkit 12.6 and download. (Need some times)
  - `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6`
- update environment variables manually.
  - Must reopen Powershell or cmd.
  - 進入 控制台 -> 編輯系統環境變數 -> 環境變數
  - 確認 CUDA_PATH 為安裝的路徑
  - 點 PATH -> 新增 (或修改舊的 v11.x -> v12.6)
    1. C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin
    2. C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\libnvvp
- use `where nvcc`, `nvcc --version` to check version is v12.6

1. Install PyTorch according to your platform: [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/)

`pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126`
=> (can skip, to run torch downgrade 2.8.0) 

1. troubleshooting

- Problem1: `pip install --upgrade setuptools` will make setuptools 82.0.1, however; torch 2.11.0+cu126 requires setuptools<82, which is incompatible.
`pip install "setuptools<82"` => Successfully installed setuptools-81.0.0
- Problem2: ERROR: Failed building wheel for torchmcubes, solved by Issue#147. =>　torch downgrade 2.8.0

```bash
pip uninstall -y torch torchvision torchaudio # skip if not do 3.
pip cache purge
pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
```

- Problem3: ModuleNotFoundError: No module named 'onnxruntime'
`pip install onnxruntime-gpu` => Successfully installed coloredlogs-15.0.1 flatbuffers-25.12.19 humanfriendly-10.0 onnxruntime-gpu-1.23.2 protobuf-7.34.1 pyreadline3-3.5.4
- Problem4:

```text
TypeError: unhashable type: 'dict'
ERROR:    Exception in ASGI application
...
ValueError: When localhost is not accessible, a shareable link must be created. Please set share=True or check your proxy settings to allow access to localhost.
```

`pip install gradio --upgrade` => ERROR: tokenizers, transformers be incompatible
`pip install transformers --upgrade` => Successfully installed tokenizers-0.22.2 transformers-5.5.4