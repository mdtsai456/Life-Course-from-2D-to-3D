# syntax=docker/dockerfile:1.4

# torchmcubes 會用 CMake 編譯 CUDA 擴充；僅安裝 PyTorch cu126 wheel 時映像內沒有 nvcc，
# 會出現「Your installed Caffe2 version uses CUDA but I cannot find the CUDA libraries」。
# 於 devel 映像內先打出 wheel，最終階段仍用 slim + PyTorch wheel（執行期不需完整 toolkit）。
FROM nvidia/cuda:12.6.0-devel-ubuntu22.04 AS torchmcubes-wheel
ENV DEBIAN_FRONTEND=noninteractive

# 部分網路會擋對 Ubuntu 鏡像的 :80；改走 HTTPS（:443）常可恢復 apt。
RUN set -e; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i \
            -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
            -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
            /etc/apt/sources.list; \
    fi; \
    if [ -d /etc/apt/sources.list.d ]; then \
        for f in /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
            [ -f "$f" ] || continue; \
            sed -i \
                -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
                -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
                "$f"; \
        done; \
    fi

# 可選：官方 Ubuntu 鏡像仍失敗時，建置傳入 --build-arg UBUNTU_MIRROR_HOST=mirrors.aliyun.com（主機名即可，勿含 http(s)://）。
ARG UBUNTU_MIRROR_HOST=
RUN if [ -n "$UBUNTU_MIRROR_HOST" ]; then \
        set -e; \
        if [ -f /etc/apt/sources.list ]; then \
            sed -i \
                -e "s|archive\\.ubuntu\\.com|$UBUNTU_MIRROR_HOST|g" \
                -e "s|security\\.ubuntu\\.com|$UBUNTU_MIRROR_HOST|g" \
                /etc/apt/sources.list; \
        fi; \
        if [ -d /etc/apt/sources.list.d ]; then \
            for f in /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
                [ -f "$f" ] || continue; \
                sed -i \
                    -e "s|archive\\.ubuntu\\.com|$UBUNTU_MIRROR_HOST|g" \
                    -e "s|security\\.ubuntu\\.com|$UBUNTU_MIRROR_HOST|g" \
                    "$f"; \
            done; \
        fi; \
    fi

# 多數「TLS non-properly terminated」在 Docker/apt 為 IPv6 路徑異常；強制 IPv4 再更新索引。
RUN printf 'Acquire::ForceIPv4 "true";\n' > /etc/apt/apt.conf.d/99force-ipv4

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-dev \
        build-essential git \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel
WORKDIR /wheels
RUN python3 -m pip install --no-cache-dir \
        torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
        --index-url https://download.pytorch.org/whl/cu126 \
    && python3 -m pip wheel --no-cache-dir \
        "git+https://github.com/tatsy/torchmcubes.git@3381600ddc3d2e4d74222f8495866be5fafbace4" \
        -w /wheels

FROM python:3.10-slim

RUN printf 'Acquire::ForceIPv4 "true";\n' > /etc/apt/apt.conf.d/99force-ipv4

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/triposr-api/requirements.txt /tmp/requirements.txt
RUN sed '/torchmcubes/d' /tmp/requirements.txt > /tmp/requirements-app.txt
COPY --from=torchmcubes-wheel /wheels/ /tmp/mcubes-wheels/

# 對齊本機驗證流程：upgrade setuptools → cu126 torch / torchvision / torchaudio → torchmcubes wheel → 其餘依賴與 onnxruntime-gpu
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir \
        torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
        --index-url https://download.pytorch.org/whl/cu126 \
    && python -m pip install --no-cache-dir /tmp/mcubes-wheels/torchmcubes-*.whl \
    && python -m pip install --no-cache-dir -r /tmp/requirements-app.txt \
    && rm -rf /tmp/mcubes-wheels

COPY services/triposr-api/triposr_api /app/triposr_api
COPY --from=triposr-main . /opt/triposr

RUN groupadd --gid 1000 triposr \
    && useradd --uid 1000 --gid triposr --home-dir /home/triposr --create-home --shell /bin/false triposr \
    && chown -R triposr:triposr /app /opt/triposr

ENV PYTHONUNBUFFERED=1
ENV TRIPOSR_SOURCE_DIR=/opt/triposr
ENV HOME=/home/triposr

USER triposr

CMD ["uvicorn", "triposr_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
