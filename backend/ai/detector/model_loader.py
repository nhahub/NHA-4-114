"""
model_loader.py
---------------
Responsible for loading and caching YOLOv8 model weights.
Handles CUDA/CPU device selection transparently.
All other AI modules import from here — never instantiate YOLO directly elsewhere.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import torch
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Module-level model cache: { model_path_str -> YOLO instance }
_MODEL_CACHE: Dict[str, YOLO] = {}


def get_device() -> str:
    """
    Return 'cuda' if a CUDA-capable GPU is available, otherwise 'cpu'.
    Logged once so operators can confirm GPU usage at startup.
    """
    if torch.cuda.is_available():
        device = "cuda"
        logger.info(
            "CUDA available — using GPU: %s",
            torch.cuda.get_device_name(0),
        )
    else:
        device = "cpu"
        logger.warning(
            "CUDA not available — falling back to CPU inference. "
            "Expect lower throughput."
        )
    return device


def load_model(model_path: str | Path, force_reload: bool = False) -> YOLO:
    """
    Load a YOLO model from *model_path* and cache it in-process.

    Parameters
    ----------
    model_path:
        Absolute or relative path to a ``.pt`` weights file.
    force_reload:
        If ``True``, bypass the cache and reload from disk.

    Returns
    -------
    YOLO
        A ready-to-use Ultralytics YOLO model instance.

    Raises
    ------
    FileNotFoundError
        When the weights file does not exist at *model_path*.
    RuntimeError
        When the model file exists but cannot be loaded (corrupt weights,
        version mismatch, etc.).
    """
    model_path = Path(model_path).resolve()
    cache_key = str(model_path)

    if not force_reload and cache_key in _MODEL_CACHE:
        logger.debug("Model cache hit: %s", cache_key)
        return _MODEL_CACHE[cache_key]

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model weights not found at '{model_path}'. "
            "Run:  yolo download yolov8n.pt  and place the file in models/."
        )

    device = get_device()
    logger.info("Loading model '%s' onto device '%s' ...", model_path.name, device)

    try:
        model = YOLO(str(model_path))
        model.to(device)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load model from '{model_path}': {exc}"
        ) from exc

    _MODEL_CACHE[cache_key] = model
    logger.info("Model loaded and cached: %s", model_path.name)
    return model


def clear_cache() -> None:
    """Remove all cached models (useful in tests or dynamic reloading scenarios)."""
    _MODEL_CACHE.clear()
    logger.debug("Model cache cleared.")
