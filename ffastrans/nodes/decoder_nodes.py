"""Decoder and filter nodes."""
import os
import json
import logging
from pathlib import Path
from .base import BaseNode
from ..core.config import FFMPEG_PATH, FFPROBE_PATH, MEDIAINFO_PATH
from ..core.models import NodeState

logger = logging.getLogger("ffastrans.nodes.decoder")


class MediaDecoder(BaseNode):
    node_type = "dec_avmedia"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))

        if not input_file or not Path(input_file).exists():
            self.log(f"Input file not found: {input_file}")
            return False

        self.log(f"Decoding/probing media: {input_file}")

        cmd = [FFPROBE_PATH, "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", input_file]
        code, stdout, stderr = self.run_command(cmd, timeout=60)

        if code != 0:
            self.log(f"Probe failed: {stderr}")
            return False

        try:
            info = json.loads(stdout)
        except json.JSONDecodeError:
            self.log("Failed to parse probe data")
            return False

        fmt = info.get("format", {})
        self.job.variables["s_duration"] = fmt.get("duration", "0")
        self.job.variables["s_file_size"] = fmt.get("size", "0")
        self.job.variables["s_format"] = fmt.get("format_name", "")
        self.job.variables["s_bitrate"] = fmt.get("bit_rate", "")

        for stream in info.get("streams", []):
            idx = stream.get("index", 0)
            codec_type = stream.get("codec_type", "")
            if codec_type == "video":
                self.job.variables[f"s_video_codec_{idx}"] = stream.get("codec_name", "")
                self.job.variables[f"s_video_width_{idx}"] = str(stream.get("width", 0))
                self.job.variables[f"s_video_height_{idx}"] = str(stream.get("height", 0))
                self.job.variables[f"s_video_fps_{idx}"] = stream.get("r_frame_rate", "")
                self.job.variables["s_video_codec"] = stream.get("codec_name", "")
                self.job.variables["s_width"] = str(stream.get("width", 0))
                self.job.variables["s_height"] = str(stream.get("height", 0))
                self.job.variables["s_fps"] = stream.get("r_frame_rate", "")
            elif codec_type == "audio":
                self.job.variables[f"s_audio_codec_{idx}"] = stream.get("codec_name", "")
                self.job.variables[f"s_audio_samplerate_{idx}"] = str(stream.get("sample_rate", ""))
                self.job.variables[f"s_audio_channels_{idx}"] = str(stream.get("channels", 0))
                self.job.variables["s_audio_codec"] = stream.get("codec_name", "")

        self.log(f"Probe complete: {fmt.get('format_name', 'unknown')}")
        return True


class StillsDecoder(BaseNode):
    node_type = "dec_stills"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            stem = Path(input_file).stem
            output_dir = self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))
            output_file = str(Path(output_dir) / f"{stem}.mp4")

        self.log(f"Converting stills to video: {input_file} -> {output_file}")

        framerate = params.get("framerate", "25")
        duration = params.get("duration", "5")
        resolution = params.get("resolution", "1920x1080")

        cmd = [FFMPEG_PATH, "-y", "-loop", "1",
               "-framerate", str(framerate),
               "-i", input_file,
               "-c:v", "libx264", "-t", str(duration),
               "-vf", f"scale={resolution.replace('x', ':')}",
               "-pix_fmt", "yuv420p", output_file]

        code, _, _ = self.run_command(cmd, timeout=300)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Stills conversion complete: {output_file}")
            return True
        self.log("Stills conversion failed")
        return False


DECODER_NODES = {
    "dec_avmedia": MediaDecoder,
    "dec_stills": StillsDecoder,
}
