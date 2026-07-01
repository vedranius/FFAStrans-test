"""Encoder nodes - all encoding via FFmpeg.

Matches original FFAStrans encoder parameters:
- Video size (WxH), display_aspect, pixel_aspect
- Resize method (stretch/fit/fill)
- Video range (full/limited)
- Color space, LUT/tone mapping
- Framerate, interlaced handling, field order
- Video bitrate, profiles, tunes, presets
- Audio tracks, format, bitrate, sample rate, conform volume
- Custom encoder options
"""
import os
import json
import logging
from .base import BaseNode
from ..core.config import FFMPEG_PATH, FFPROBE_PATH
from ..core.models import NodeState

logger = logging.getLogger('ffastrans.nodes.encoder')


class BaseEncoder(BaseNode):
    def _get_media_info(self, input_file: str) -> dict:
        cmd = [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json',
               '-show_format', '-show_streams', input_file]
        code, stdout, stderr = self.run_command(cmd, timeout=30)
        if code == 0:
            try:
                return json.loads(stdout)
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    def _get_duration(self, input_file: str) -> float:
        info = self._get_media_info(input_file)
        return float(info.get('format', {}).get('duration', 0))

    def _build_video_filter_chain(self, params: dict, input_info: dict = None) -> list[str]:
        filters = []
        w = params.get('video_width', '')
        h = params.get('video_height', '')
        resize_method = params.get('resize_method', 'stretch')

        if w and h:
            if resize_method == 'fit':
                filters.append(f'scale={w}:{h}:force_original_aspect_ratio=decrease')
                filters.append(f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black')
            elif resize_method == 'fill':
                filters.append(f'scale={w}:{h}:force_original_aspect_ratio=increase')
                filters.append(f'crop={w}:{h}')
            else:
                filters.append(f'scale={w}:{h}')

        fps = params.get('framerate', '')
        if fps:
            filters.append(f'fps={fps}')

        deinterlace = params.get('deinterlace', False)
        if deinterlace:
            filters.append('yadif=0:-1:0')

        return filters

    def _build_video_opts(self, params: dict, input_info: dict = None) -> list[str]:
        opts = []
        vcodec = params.get('vcodec', 'libx264')
        opts.extend(['-c:v', vcodec])

        if params.get('video_bitrate'):
            opts.extend(['-b:v', str(params['video_bitrate'])])
        if params.get('max_bitrate'):
            opts.extend(['-maxrate', str(params['max_bitrate'])])
        if params.get('bufsize'):
            opts.extend(['-bufsize', str(params['bufsize'])])
        if params.get('crf') is not None:
            opts.extend(['-crf', str(params['crf'])])
        if params.get('video_preset'):
            opts.extend(['-preset', str(params['video_preset'])])
        if params.get('pixel_format'):
            opts.extend(['-pix_fmt', str(params['pixel_format'])])
        if params.get('video_profile'):
            opts.extend(['-profile:v', str(params['video_profile'])])
        if params.get('level'):
            opts.extend(['-level', str(params['level'])])
        if params.get('tune'):
            opts.extend(['-tune', str(params['tune'])])
        if params.get('video_range') == 'limited':
            opts.extend(['-color_range', 'tv'])
        elif params.get('video_range') == 'full':
            opts.extend(['-color_range', 'pc'])

        color_space = params.get('color_space', '')
        if color_space:
            cs_map = {
                'bt709': 'bt709', 'bt601': 'bt470bg',
                'bt2020': 'bt2020nc', 'smpte170': 'smpte170m',
            }
            if color_space in cs_map:
                opts.extend(['-colorspace', cs_map[color_space]])

        if params.get('faststart'):
            opts.extend(['-movflags', '+faststart'])

        custom_x264 = params.get('custom_x264_options', '')
        if custom_x264 and vcodec == 'libx264':
            opts.extend(['-x264-params', custom_x264])

        custom_x265 = params.get('custom_x265_options', '')
        if custom_x265 and vcodec == 'libx265':
            opts.extend(['-x265-params', custom_x265])

        return opts

    def _build_audio_opts(self, params: dict) -> list[str]:
        opts = []
        a_disabled = params.get('audio_disabled', False)
        if a_disabled:
            opts.extend(['-an'])
            return opts

        acodec = params.get('acodec')
        if acodec:
            opts.extend(['-c:a', acodec])

        if params.get('audio_bitrate'):
            opts.extend(['-b:a', str(params['audio_bitrate'])])
        if params.get('audio_sample_rate'):
            opts.extend(['-ar', str(params['audio_sample_rate'])])
        if params.get('audio_channels'):
            opts.extend(['-ac', str(params['audio_channels'])])

        conform_volume = params.get('conform_volume', '')
        if conform_volume:
            vol = float(conform_volume)
            if vol != 0:
                opts.extend(['-af', f'volume={vol}dB'])

        return opts

    def _get_output_path(self, params: dict, input_file: str, default_ext: str) -> str:
        output = self.resolve(params.get('output', ''))
        if output:
            return output
        from pathlib import Path
        stem = Path(input_file).stem
        output_dir = self.resolve(params.get('output_dir', ''))
        if not output_dir:
            output_dir = self.resolve(params.get('work_folder', ''))
        if not output_dir:
            output_dir = os.getenv('FFASTRANS_OUTPUT_DIR', 'drop_folders/output')
        return str(Path(output_dir) / f'{stem}{default_ext}')

    def _build_scale_filter(self, params: dict) -> str:
        w = params.get('video_width', '')
        h = params.get('video_height', '')
        method = params.get('resize_method', 'stretch')
        if not w and not h:
            return ''
        if method == 'fit':
            return f'scale={w or -1}:{h or -1}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black'
        elif method == 'fill':
            return f'scale={w or -1}:{h or -1}:force_original_aspect_ratio=increase,crop={w}:{h}'
        return f'scale={w or -1}:{h or -1}'


class H264MP4Encoder(BaseEncoder):
    """H.264/MP4 encoder - matches original enc_av_mp4."""
    node_type = 'enc_av_mp4'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mp4')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding H264/MP4: {input_file} -> {output_file}')

        input_info = self._get_media_info(input_file)
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [FFMPEG_PATH, '-y', '-i', input_file]

        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if params.get('deinterlace'):
            vf_parts.append('yadif=0:-1:0')
        fps = params.get('framerate', '')
        if fps:
            vf_parts.append(f'fps={fps}')
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend(self._build_video_opts(params, input_info))
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?', '-map', '0:s?'])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class H265Encoder(BaseEncoder):
    """H.265/HEVC encoder - matches original enc_av_265."""
    node_type = 'enc_av_265'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mp4')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding H265/HEVC: {input_file} -> {output_file}')

        input_info = self._get_media_info(input_file)
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [FFMPEG_PATH, '-y', '-i', input_file]

        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if params.get('deinterlace'):
            vf_parts.append('yadif=0:-1:0')
        fps = params.get('framerate', '')
        if fps:
            vf_parts.append(f'fps={fps}')
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend(self._build_video_opts(params, input_info))

        if params.get('hdr'):
            cmd.extend([
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084',
                '-colorspace', 'bt2020nc',
            ])

        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?', '-map', '0:s?'])
        cmd.extend(['-movflags', '+faststart', output_file])

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class ProResEncoder(BaseEncoder):
    """Apple ProRes encoder - matches original enc_av_prores."""
    node_type = 'enc_av_prores'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mov')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding ProRes: {input_file} -> {output_file}')

        input_info = self._get_media_info(input_file)
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        profile = params.get('profile', '3')
        profile_map = {
            '0': 'proxy', '1': 'lt', '2': 'standard', '3': 'hq',
            '4': '4444', '5': '4444xq',
        }
        profile_name = profile_map.get(str(profile), 'hq')

        processing_mode = params.get('processing_mode', '')

        cmd = [FFMPEG_PATH, '-y', '-i', input_file]

        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        pix_fmt = params.get('pixel_format', 'yuv422p10le')
        cmd.extend([
            '-c:v', 'prores_ks',
            '-profile:v', profile_name,
            '-pix_fmt', pix_fmt,
        ])
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?'])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class DNxHREncoder(BaseEncoder):
    """Avid DNxHR encoder."""
    node_type = 'enc_av_dnxhr'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mxf')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding DNxHR: {input_file} -> {output_file}')

        input_info = self._get_media_info(input_file)
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        dnxhr_profile = params.get('dnxhr_profile', 'DNxHR HQ')
        cmd = [FFMPEG_PATH, '-y', '-i', input_file]

        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend([
            '-c:v', 'dnxhd',
            '-profile:v', dnxhr_profile,
            '-pix_fmt', params.get('pixel_format', 'yuv422p'),
        ])
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?'])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class DNxHDEncoder(BaseEncoder):
    """Avid DNxHD encoder."""
    node_type = 'enc_av_dnxhd'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mxf')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding DNxHD: {input_file} -> {output_file}')

        input_info = self._get_media_info(input_file)
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        dnxhd_profile = params.get('dnxhd_profile', 'DNxHD 185')
        cmd = [FFMPEG_PATH, '-y', '-i', input_file]

        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend([
            '-c:v', 'dnxhd',
            '-profile:v', dnxhd_profile,
        ])
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?'])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class CustomFFmpegEncoder(BaseEncoder):
    """Custom FFmpeg arguments encoder."""
    node_type = 'enc_av_customff'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        custom_args = self.resolve(params.get('ffmpeg_args', ''))
        output_file = self._get_output_path(params, input_file, '_out.mp4')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Custom FFmpeg encoding: {input_file} -> {output_file}')
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [FFMPEG_PATH, '-y', '-i', input_file]
        if custom_args:
            cmd.extend(custom_args.split())
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class AudioEncoder(BaseEncoder):
    """Audio-only encoding node."""
    node_type = 'enc_a_audio'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '_audio.wav')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Audio encoding: {input_file} -> {output_file}')
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [FFMPEG_PATH, '-y', '-i', input_file, '-vn']
        acodec = params.get('acodec', 'pcm_s16le')
        cmd.extend(['-c:a', acodec])
        if params.get('audio_sample_rate'):
            cmd.extend(['-ar', str(params['audio_sample_rate'])])
        if params.get('audio_channels'):
            cmd.extend(['-ac', str(params['audio_channels'])])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=3600)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Audio encoding complete: {output_file}')
            return True
        self.log('Audio encoding failed')
        return False


class XDCAMEncoder(BaseEncoder):
    """Sony XDCAM HD encoder."""
    node_type = 'enc_av_xdcamhd'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mxf')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding XDCAM HD: {input_file} -> {output_file}')
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [FFMPEG_PATH, '-y', '-i', input_file]
        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend([
            '-c:v', 'mpeg2video',
            '-b:v', params.get('video_bitrate', '50M'),
            '-maxrate', params.get('max_bitrate', '50M'),
            '-bufsize', params.get('bufsize', '50M'),
        ])
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?'])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


class AV1Encoder(BaseEncoder):
    """AV1 encoder."""
    node_type = 'enc_av_av1'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self._get_output_path(params, input_file, '.mkv')

        if not input_file or not os.path.exists(input_file):
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Encoding AV1: {input_file} -> {output_file}')
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [FFMPEG_PATH, '-y', '-i', input_file]
        vf_parts = []
        scale = self._build_scale_filter(params)
        if scale:
            vf_parts.append(scale)
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend(['-c:v', 'libsvtav1'])
        if params.get('crf'):
            cmd.extend(['-crf', str(params['crf'])])
        else:
            cmd.extend(['-crf', '30'])
        if params.get('video_preset'):
            cmd.extend(['-preset', str(params['video_preset'])])
        cmd.extend(self._build_audio_opts(params))
        cmd.extend(['-map', '0:v?', '-map', '0:a?'])
        cmd.append(output_file)

        code, _, _ = self.run_command(cmd, timeout=7200)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Encoding complete: {output_file}')
            return True
        self.log('Encoding failed')
        return False


ENCODER_NODES = {
    'enc_av_mp4': H264MP4Encoder,
    'enc_av_265': H265Encoder,
    'enc_av_prores': ProResEncoder,
    'enc_av_dnxhr': DNxHREncoder,
    'enc_av_dnxhd': DNxHDEncoder,
    'enc_av_xdcamhd': XDCAMEncoder,
    'enc_av_av1': AV1Encoder,
    'enc_av_customff': CustomFFmpegEncoder,
    'enc_a_audio': AudioEncoder,
}
