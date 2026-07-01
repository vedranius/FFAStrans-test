"""Encoder nodes - all encoding via FFmpeg."""
import os
import json
import logging
from .base import BaseNode
from ..core.config import FFMPEG_PATH, FFPROBE_PATH
from ..core.models import NodeState

logger = logging.getLogger("ffastrans.nodes.encoder")


class BaseEncoder(BaseNode):
    def _get_duration(self, input_file: str) -> float:
        cmd = [FFPROBE_PATH, "-v", "quiet", "-print_format", "json", "-show_format", input_file]
        code, stdout, stderr = self.run_command(cmd, timeout=30)
        if code == 0:
            try:
                info = json.loads(stdout)
                return float(info.get("format", {}).get("duration", 0))
            except (json.JSONDecodeError, ValueError):
                pass
        return 0.0

    def _build_video_opts(self, params: dict) -> list[str]:
        opts = []
        vcodec = params.get("vcodec", "libx264")
        opts.extend(["-c:v", vcodec])

        if params.get("bitrate"):
            opts.extend(["-b:v", str(params["bitrate"])])
        if params.get("crf"):
            opts.extend(["-crf", str(params["crf"])])
        if params.get("preset"):
            opts.extend(["-preset", str(params["preset"])])
        if params.get("pixel_format"):
            opts.extend(["-pix_fmt", str(params["pixel_format"])])
        if params.get("resolution"):
            opts.extend(["-vf", f"scale={params['resolution']}"])
        if params.get("framerate"):
            opts.extend(["-r", str(params["framerate"])])
        if params.get("maxrate"):
            opts.extend(["-maxrate", str(params["maxrate"])])
        if params.get("bufsize"):
            opts.extend(["-bufsize", str(params["bufsize"])])
        if params.get("profile"):
            opts.extend(["-profile:v", str(params["profile"])])
        if params.get("level"):
            opts.extend(["-level", str(params["level"])])
        if params.get("tune"):
            opts.extend(["-tune", str(params["tune"])])
        return opts

    def _build_audio_opts(self, params: dict) -> list[str]:
        opts = []
        acodec = params.get("acodec")
        if acodec:
            opts.extend(["-c:a", acodec])
        if params.get("audio_bitrate"):
            opts.extend(["-b:a", str(params["audio_bitrate"])])
        if params.get("audio_sample_rate"):
            opts.extend(["-ar", str(params["audio_sample_rate"])])
        if params.get("audio_channels"):
            opts.extend(["-ac", str(params["audio_channels"])])
        return opts


class H264MP4Encoder(BaseEncoder):
    node_type = "enc_av_mp4"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))) / f"{stem}.mp4")

        self.log(f"Encoding H264/MP4: {input_file} -> {output_file}")

        cmd = [FFMPEG_PATH, "-y", "-i", input_file]
        cmd.extend(self._build_video_opts({
            "vcodec": params.get("vcodec", "libx264"),
            "bitrate": params.get("video_bitrate", "5M"),
            "preset": params.get("preset", "medium"),
            "crf": params.get("crf", "23"),
            "pixel_format": params.get("pixel_format", "yuv420p"),
            "profile": params.get("profile", "high"),
            "level": params.get("level", "4.1"),
        }))
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(["-movflags", "+faststart", output_file])

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Encoding complete: {output_file}")
            return True
        self.log("Encoding failed")
        return False


class H265Encoder(BaseEncoder):
    node_type = "enc_av_265"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))) / f"{stem}.mp4")

        self.log(f"Encoding H265/HEVC: {input_file} -> {output_file}")

        cmd = [FFMPEG_PATH, "-y", "-i", input_file]
        cmd.extend(["-c:v", "libx265"])
        if params.get("crf"):
            cmd.extend(["-crf", str(params["crf"])])
        else:
            cmd.extend(["-crf", "28"])
        if params.get("preset"):
            cmd.extend(["-preset", str(params["preset"])])
        if params.get("pixel_format"):
            cmd.extend(["-pix_fmt", str(params["pixel_format"])])
        if params.get("hdr"):
            cmd.extend(["-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc"])
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(["-movflags", "+faststart", output_file])

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Encoding complete: {output_file}")
            return True
        self.log("Encoding failed")
        return False


class ProResEncoder(BaseEncoder):
    node_type = "enc_av_prores"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))) / f"{stem}.mov")

        self.log(f"Encoding ProRes: {input_file} -> {output_file}")

        profile = params.get("profile", "5")
        profile_map = {"0": "proxy", "1": "lt", "2": "standard", "3": "hq"}
        profile_name = profile_map.get(str(profile), "hq")

        cmd = [FFMPEG_PATH, "-y", "-i", input_file,
               "-c:v", "prores_ks", "-profile:v", profile_name,
               "-pix_fmt", params.get("pixel_format", "yuv422p10le")]
        cmd.extend(self._build_audio_opts(params))
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Encoding complete: {output_file}")
            return True
        self.log("Encoding failed")
        return False


class DNxHREncoder(BaseEncoder):
    node_type = "enc_av_dnxhr"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))) / f"{stem}.mxf")

        self.log(f"Encoding DNxHR: {input_file} -> {output_file}")

        dnxhr_profile = params.get("dnxhr_profile", "DNxHR HQ")
        cmd = [FFMPEG_PATH, "-y", "-i", input_file,
               "-c:v", "dnxhd", "-profile:v", dnxhr_profile,
               "-pix_fmt", params.get("pixel_format", "yuv422p")]
        cmd.extend(self._build_audio_opts(params))
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Encoding complete: {output_file}")
            return True
        self.log("Encoding failed")
        return False


class CustomFFmpegEncoder(BaseEncoder):
    node_type = "enc_av_customff"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        custom_args = self.resolve(params.get("ffmpeg_args", ""))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))) / f"{stem}_out.mp4")

        cmd = [FFMPEG_PATH, "-y", "-i", input_file]
        if custom_args:
            cmd.extend(custom_args.split())
        cmd.append(output_file)

        self.log(f"Custom FFmpeg encoding: {input_file} -> {output_file}")
        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Encoding complete: {output_file}")
            return True
        self.log("Encoding failed")
        return False


class AudioEncoder(BaseEncoder):
    node_type = "enc_a_audio"

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get("input", self.job.input_file))
        output_file = self.resolve(params.get("output", ""))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(self.resolve(params.get("output_dir", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))) / f"{stem}_audio.wav")

        self.log(f"Audio encoding: {input_file} -> {output_file}")

        cmd = [FFMPEG_PATH, "-y", "-i", input_file, "-vn"]
        acodec = params.get("acodec", "pcm_s16le")
        cmd.extend(["-c:a", acodec])
        if params.get("audio_sample_rate"):
            cmd.extend(["-ar", str(params["audio_sample_rate"])])
        if params.get("audio_channels"):
            cmd.extend(["-ac", str(params["audio_channels"])])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=3600)
        if code == 0:
            self.job.variables["s_output_file"] = output_file
            self.log(f"Audio encoding complete: {output_file}")
            return True
        self.log("Audio encoding failed")
        return False


ENCODER_NODES = {
    "enc_av_mp4": H264MP4Encoder,
    "enc_av_265": H265Encoder,
    "enc_av_prores": ProResEncoder,
    "enc_av_dnxhr": DNxHREncoder,
    "enc_av_customff": CustomFFmpegEncoder,
    "enc_a_audio": AudioEncoder,
}
