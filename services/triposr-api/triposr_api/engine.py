"""Thin wrapper around the TripoSR inference pipeline."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock

from triposr_api.settings import Settings, get_settings


class EngineNotReadyError(RuntimeError):
    """Raised when the engine is not available for inference."""


class InvalidImageError(RuntimeError):
    """Raised when an upload cannot be decoded as an image."""


class EmptyMeshError(RuntimeError):
    """Raised when TripoSR produces an effectively empty mesh."""


class InferenceFailedError(RuntimeError):
    """Raised when TripoSR inference fails."""


@dataclass
class EngineHealth:
    ready: bool
    detail: str | None = None


class TriposrEngine:
    """Owns model state and exposes a small infer_glb boundary."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = Lock()
        self._startup_error: str | None = None
        self._device: str | None = None
        self._torch = None
        self._model = None
        self._rembg_session = None
        self._remove_background = None
        self._resize_foreground = None

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return

            try:
                source_dir = Path(self.settings.source_dir)
                if not (source_dir / "tsr").exists():
                    raise RuntimeError(
                        f"找不到 TripoSR 原始碼目錄：{source_dir}"
                    )
                if str(source_dir) not in sys.path:
                    sys.path.insert(0, str(source_dir))

                import rembg
                import torch

                from tsr.system import TSR
                from tsr.utils import remove_background, resize_foreground

                if not torch.cuda.is_available():
                    raise RuntimeError("目前沒有可用的 CUDA GPU。")

                model = TSR.from_pretrained(
                    self.settings.pretrained_model_name_or_path,
                    config_name="config.yaml",
                    weight_name="model.ckpt",
                )
                model.renderer.set_chunk_size(self.settings.chunk_size)
                model.to(self.settings.device)

                self._device = self.settings.device
                self._torch = torch
                self._model = model
                self._rembg_session = rembg.new_session()
                self._remove_background = remove_background
                self._resize_foreground = resize_foreground
                self._startup_error = None
            except Exception as exc:
                self._startup_error = str(exc)
                self._model = None
                raise

    def health(self) -> EngineHealth:
        with self._lock:
            return EngineHealth(
                ready=self._model is not None,
                detail=self._startup_error,
            )

    def infer_glb(self, image_bytes: bytes) -> bytes:
        with self._lock:
            if self._model is None or self._torch is None or self._device is None:
                raise EngineNotReadyError(
                    self._startup_error or "3D 推理服務尚未就緒。"
                )

            image = self._decode_image(image_bytes)
            prepared = self._prepare_image(image)

            try:
                with self._torch.no_grad():
                    scene_codes = self._model([prepared], device=self._device)
                mesh = self._model.extract_mesh(
                    scene_codes,
                    True,
                    resolution=self.settings.mc_resolution,
                )[0]
            except Exception as exc:
                raise InferenceFailedError("TripoSR 推理失敗。") from exc

            self._validate_mesh(mesh)

            try:
                glb = mesh.export(file_type="glb")
            except Exception as exc:
                raise InferenceFailedError("GLB 匯出失敗。") from exc

            if not isinstance(glb, (bytes, bytearray)) or len(glb) == 0:
                raise InferenceFailedError("GLB 匯出失敗。")

            return bytes(glb)

    def _decode_image(self, image_bytes: bytes):
        from PIL import Image, ImageOps

        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
        except OSError as exc:
            raise InvalidImageError("檔案內容不是有效的圖片格式。") from exc

        return self._resize_if_needed(ImageOps.exif_transpose(image))

    def _prepare_image(self, image):
        import numpy as np
        from PIL import Image

        base_image = image.convert("RGB")

        if self._remove_background is None or self._resize_foreground is None:
            raise EngineNotReadyError("3D 推理服務尚未就緒。")

        rgba_image = self._remove_background(base_image, self._rembg_session)
        rgba_image = self._resize_foreground(
            rgba_image,
            self.settings.foreground_ratio,
        )

        image_array = np.array(rgba_image).astype(np.float32) / 255.0
        image_array = (
            image_array[:, :, :3] * image_array[:, :, 3:4]
            + (1 - image_array[:, :, 3:4]) * 0.5
        )
        return Image.fromarray((image_array * 255.0).astype(np.uint8))

    def _resize_if_needed(self, image):
        from PIL import Image

        max_edge = max(image.size)
        if max_edge <= self.settings.max_image_edge:
            return image

        image = image.copy()
        image.thumbnail(
            (self.settings.max_image_edge, self.settings.max_image_edge),
            Image.Resampling.LANCZOS,
        )
        return image

    def _validate_mesh(self, mesh) -> None:
        vertices = getattr(mesh, "vertices", [])
        faces = getattr(mesh, "faces", [])
        if len(vertices) < 4 or len(faces) < 4:
            raise EmptyMeshError("產生的 3D 模型內容不足，請換一張圖片再試。")


class DegradedEngine:
    """Minimal engine stand-in when settings or construction fails at startup."""

    def __init__(self, detail: str) -> None:
        self._detail = detail

    def load(self) -> None:
        return None

    def health(self) -> EngineHealth:
        return EngineHealth(ready=False, detail=self._detail)

    def infer_glb(self, image_bytes: bytes) -> bytes:
        raise EngineNotReadyError(
            self._detail or "3D 推理服務尚未就緒。"
        )


def build_engine() -> TriposrEngine:
    return TriposrEngine(get_settings())
