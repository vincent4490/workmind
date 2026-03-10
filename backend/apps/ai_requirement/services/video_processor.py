# -*- coding: utf-8 -*-
"""
视频关键帧抽取服务

基于 FFmpeg 和 OpenCV 从上传视频中抽取关键帧 + 可选 ASR 文字提取。
支持 .mp4 / .avi / .mov / .webm 格式。

依赖：
- ffmpeg（系统级，需 PATH 可访问）
- opencv-contrib-python（已在 requirements.txt）
- Pillow（已在 requirements.txt）

可选 ASR：在 settings 中配置 AI_REQUIREMENT_ASR_ENABLED=True 与 AI_REQUIREMENT_ASR_API_URL，
将视频音轨提取为 16kHz 单声道 WAV 后 POST 到该 URL，预期返回 JSON {"text": "转写内容"} 或纯文本。
"""
import base64
import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)

SUPPORTED_VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.webm', '.mkv'}
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_KEYFRAMES = 10
KEYFRAME_MAX_DIMENSION = 1024
KEYFRAME_QUALITY = 80


class VideoProcessError(Exception):
    pass


class VideoProcessor:
    """
    视频关键帧抽取器

    process_video(file) 返回:
    {
        "keyframes": [{"index": 0, "timestamp_s": 1.5, "data": "base64", "mime": "image/jpeg"}],
        "metadata": {"duration_s": 120, "fps": 30, "width": 1920, "height": 1080},
        "transcript": "ASR文字（如果可用）",
        "warnings": []
    }
    """

    @staticmethod
    def is_video_file(filename: str) -> bool:
        return Path(filename).suffix.lower() in SUPPORTED_VIDEO_EXTS

    @staticmethod
    def check_ffmpeg() -> bool:
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def process_video(self, uploaded_file) -> dict:
        """
        从上传的视频文件中抽取关键帧

        Args:
            uploaded_file: Django UploadedFile 对象

        Returns:
            dict: 关键帧列表、元数据、ASR文字
        """
        filename = uploaded_file.name if hasattr(uploaded_file, 'name') else 'video.mp4'
        file_size = uploaded_file.size if hasattr(uploaded_file, 'size') else 0

        if file_size > MAX_VIDEO_SIZE:
            raise VideoProcessError(f'视频文件过大（>{MAX_VIDEO_SIZE // 1024 // 1024}MB）: {filename}')

        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTS:
            raise VideoProcessError(f'不支持的视频格式: {ext}')

        warnings = []

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)

        try:
            metadata = self._get_video_metadata(tmp_path)

            if self.check_ffmpeg():
                keyframes = self._extract_keyframes_ffmpeg(tmp_path, metadata)
            else:
                warnings.append('FFmpeg 不可用，降级使用 OpenCV 抽帧')
                keyframes = self._extract_keyframes_opencv(tmp_path, metadata)

            if len(keyframes) > MAX_KEYFRAMES:
                keyframes = keyframes[:MAX_KEYFRAMES]
                warnings.append(f'关键帧数量超限，仅保留前 {MAX_KEYFRAMES} 帧')

            transcript = self._run_asr(tmp_path)
            if transcript and not transcript.strip():
                transcript = ''

            return {
                'keyframes': keyframes,
                'metadata': metadata,
                'transcript': transcript,
                'warnings': warnings,
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def process_video_from_path(self, video_path: str) -> dict:
        """从本地路径处理视频"""
        if not os.path.exists(video_path):
            raise VideoProcessError(f'视频文件不存在: {video_path}')

        filename = os.path.basename(video_path)
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTS:
            raise VideoProcessError(f'不支持的视频格式: {ext}')

        file_size = os.path.getsize(video_path)
        if file_size > MAX_VIDEO_SIZE:
            raise VideoProcessError(f'视频文件过大: {file_size // 1024 // 1024}MB')

        warnings = []
        metadata = self._get_video_metadata(video_path)

        if self.check_ffmpeg():
            keyframes = self._extract_keyframes_ffmpeg(video_path, metadata)
        else:
            warnings.append('FFmpeg 不可用，降级使用 OpenCV 抽帧')
            keyframes = self._extract_keyframes_opencv(video_path, metadata)

        if len(keyframes) > MAX_KEYFRAMES:
            keyframes = keyframes[:MAX_KEYFRAMES]

        transcript = self._run_asr(video_path)
        if transcript and not transcript.strip():
            transcript = ''

        return {
            'keyframes': keyframes,
            'metadata': metadata,
            'transcript': transcript,
            'warnings': warnings,
        }

    def _run_asr(self, video_path: str) -> str:
        """
        可选 ASR：若配置了 AI_REQUIREMENT_ASR_API_URL，则提取音轨并 POST 到该接口获取转写文本。

        期望接口：POST multipart/form-data 或 application/octet-stream，返回 JSON {"text": "..."} 或纯文本。
        """
        try:
            enabled = getattr(settings, 'AI_REQUIREMENT_ASR_ENABLED', False)
            api_url = (getattr(settings, 'AI_REQUIREMENT_ASR_API_URL', None) or '').strip()
            if not enabled or not api_url:
                return ''
        except Exception:
            return ''

        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                wav_path = f.name
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                wav_path, '-y', '-loglevel', 'error',
            ]
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)

            import urllib.request
            with open(wav_path, 'rb') as af:
                data = af.read()
            req = urllib.request.Request(
                api_url,
                data=data,
                method='POST',
                headers={'Content-Type': 'audio/wav'},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode('utf-8', errors='ignore').strip()
            try:
                import json
                out = json.loads(body)
                return (out.get('text') or out.get('transcript') or '').strip()
            except (json.JSONDecodeError, TypeError):
                return body if body else ''
        except subprocess.CalledProcessError as e:
            logger.warning(f'[VideoProcessor] ASR 音轨提取失败: {e.stderr.decode()[:200] if e.stderr else e}')
            return ''
        except Exception as e:
            logger.warning(f'[VideoProcessor] ASR 调用失败: {e}')
            return ''
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

    def _get_video_metadata(self, video_path: str) -> dict:
        """获取视频元信息"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise VideoProcessError('无法打开视频文件')

            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            duration_s = frame_count / fps if fps > 0 else 0
            cap.release()

            return {
                'duration_s': round(duration_s, 2),
                'fps': round(fps, 2),
                'frame_count': frame_count,
                'width': width,
                'height': height,
            }
        except ImportError:
            return {'duration_s': 0, 'fps': 0, 'frame_count': 0, 'width': 0, 'height': 0}

    def _extract_keyframes_ffmpeg(self, video_path: str, metadata: dict) -> list:
        """
        使用 FFmpeg 场景检测抽取关键帧

        策略：先用场景检测（scdet），如果帧太少则均匀抽帧
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            out_pattern = os.path.join(tmpdir, 'frame_%04d.jpg')

            duration = metadata.get('duration_s', 0)
            if duration <= 0:
                duration = 60

            # 均匀抽帧：每 N 秒一帧，确保 5-10 帧
            interval = max(duration / MAX_KEYFRAMES, 2)

            cmd = [
                'ffmpeg', '-i', video_path,
                '-vf', f'fps=1/{interval:.1f},scale={KEYFRAME_MAX_DIMENSION}:-1',
                '-q:v', '3',
                '-frames:v', str(MAX_KEYFRAMES),
                out_pattern,
                '-y', '-loglevel', 'error',
            ]

            try:
                subprocess.run(cmd, capture_output=True, timeout=60, check=True)
            except subprocess.CalledProcessError as e:
                logger.warning(f'[VideoProcessor] FFmpeg 抽帧失败: {e.stderr.decode()[:200]}')
                return self._extract_keyframes_opencv(video_path, metadata)
            except subprocess.TimeoutExpired:
                logger.warning('[VideoProcessor] FFmpeg 抽帧超时')
                return self._extract_keyframes_opencv(video_path, metadata)

            frames = sorted(Path(tmpdir).glob('frame_*.jpg'))
            keyframes = []
            for idx, frame_path in enumerate(frames):
                b64 = self._image_to_base64(str(frame_path))
                if b64:
                    timestamp_s = round(idx * interval, 2)
                    keyframes.append({
                        'index': idx,
                        'timestamp_s': timestamp_s,
                        'data': b64,
                        'mime': 'image/jpeg',
                    })

            return keyframes

    def _extract_keyframes_opencv(self, video_path: str, metadata: dict) -> list:
        """使用 OpenCV 均匀抽帧（FFmpeg 不可用时的降级方案）"""
        try:
            import cv2
        except ImportError:
            raise VideoProcessError('OpenCV 未安装，无法处理视频')

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise VideoProcessError('无法打开视频文件')

        frame_count = metadata.get('frame_count', 0)
        if frame_count <= 0:
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        fps = metadata.get('fps', 30) or 30
        num_frames = min(MAX_KEYFRAMES, max(5, frame_count // int(fps * 5)))
        interval = max(frame_count // num_frames, 1) if num_frames > 0 else frame_count

        keyframes = []
        for i in range(num_frames):
            frame_idx = i * interval
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            if max(h, w) > KEYFRAME_MAX_DIMENSION:
                scale = KEYFRAME_MAX_DIMENSION / max(h, w)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, KEYFRAME_QUALITY])
            b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

            timestamp_s = round(frame_idx / fps, 2) if fps > 0 else 0.0
            keyframes.append({
                'index': len(keyframes),
                'timestamp_s': timestamp_s,
                'data': b64,
                'mime': 'image/jpeg',
            })

        cap.release()
        return keyframes

    def _image_to_base64(self, image_path: str) -> str | None:
        """将图片文件转为 base64"""
        try:
            img = Image.open(image_path)
            w, h = img.size
            if max(w, h) > KEYFRAME_MAX_DIMENSION:
                ratio = KEYFRAME_MAX_DIMENSION / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

            buf = io.BytesIO()
            img.convert('RGB').save(buf, format='JPEG', quality=KEYFRAME_QUALITY)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception as e:
            logger.warning(f'[VideoProcessor] 图片转 base64 失败: {e}')
            return None
