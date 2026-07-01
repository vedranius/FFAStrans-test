"""Decoder nodes - media probing and decoding via FFmpeg.

Matches original FFAStrans decoders:
- dec_avmedia: Media decoder/prober (FFprobe-based, no AviSynth on Linux)
- dec_stills: Stills to video conversion
- dec_youtube: YouTube/video URL decoder (via yt-dlp)
"""
import os
import json
import logging
from pathlib import Path
from .base import BaseNode
from ..core.config import FFMPEG_PATH, FFPROBE_PATH

logger = logging.getLogger('ffastrans.nodes.decoder')


class MediaDecoder(BaseNode):
    """Media decoder/prober node - probes file and populates media variables.

    Matches original FFAStrans dec_avmedia:
    - use_video, video_decode (none/intelligent/full)
    - use_audio, audio_decode
    - Populates: i_width, i_height, f_fps, s_v_codec, s_a_codec
    - Populates: o_media (full JSON probe data)
    """
    node_type = 'dec_avmedia'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))

        if not input_file or not Path(input_file).exists():
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Decoding/probing media: {input_file}')

        cmd = [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json',
               '-show_format', '-show_streams', '-show_frames', input_file]
        code, stdout, stderr = self.run_command(cmd, timeout=60)

        if code != 0:
            self.log(f'Probe failed: {stderr}')
            return False

        try:
            info = json.loads(stdout)
        except json.JSONDecodeError:
            self.log('Failed to parse probe data')
            return False

        fmt = info.get('format', {})
        streams = info.get('streams', [])

        self.job.variables['f_duration'] = fmt.get('duration', '0')
        self.job.variables['i_file_size'] = fmt.get('size', '0')
        self.job.variables['s_format'] = fmt.get('format_name', '')
        self.job.variables['s_bitrate'] = fmt.get('bit_rate', '')
        self.job.variables['s_filename'] = Path(input_file).name

        self.var_engine.set_job_var('f_duration', fmt.get('duration', '0'))
        self.var_engine.set_job_var('i_file_size', fmt.get('size', '0'))
        self.var_engine.set_job_var('s_format', fmt.get('format_name', ''))

        video_count = 0
        audio_count = 0
        for stream in streams:
            idx = stream.get('index', 0)
            codec_type = stream.get('codec_type', '')

            if codec_type == 'video':
                self.job.variables['s_v_codec'] = stream.get('codec_name', '')
                self.job.variables['i_width'] = str(stream.get('width', 0))
                self.job.variables['i_height'] = str(stream.get('height', 0))
                self.job.variables['f_fps'] = stream.get('r_frame_rate', '')
                self.job.variables['s_pix_fmt'] = stream.get('pix_fmt', '')
                self.job.variables['i_v_bitrate'] = str(stream.get('bit_rate', ''))
                self.job.variables['i_frames'] = str(stream.get('nb_frames', ''))
                self.job.variables['s_color_space'] = stream.get('color_space', '')
                self.job.variables['s_color_range'] = stream.get('color_range', '')
                self.job.variables['s_field_order'] = stream.get('field_order', '')

                self.var_engine.set_job_var('s_v_codec', stream.get('codec_name', ''))
                self.var_engine.set_job_var('i_width', str(stream.get('width', 0)))
                self.var_engine.set_job_var('i_height', str(stream.get('height', 0)))
                self.var_engine.set_job_var('f_fps', stream.get('r_frame_rate', ''))
                self.var_engine.set_job_var('s_pix_fmt', stream.get('pix_fmt', ''))

                video_count += 1

            elif codec_type == 'audio':
                self.job.variables['s_a_codec'] = stream.get('codec_name', '')
                self.job.variables['i_a_bitrate'] = str(stream.get('bit_rate', ''))
                self.job.variables['i_sample_rate'] = str(stream.get('sample_rate', ''))
                self.job.variables['i_channels'] = str(stream.get('channels', 0))
                self.job.variables['s_channel_layout'] = stream.get('channel_layout', '')

                self.var_engine.set_job_var('s_a_codec', stream.get('codec_name', ''))
                self.var_engine.set_job_var('i_sample_rate', str(stream.get('sample_rate', '')))
                self.var_engine.set_job_var('i_channels', str(stream.get('channels', 0)))

                audio_count += 1

        self.job.variables['i_video_streams'] = str(video_count)
        self.job.variables['i_audio_streams'] = str(audio_count)

        try:
            self.job.variables['o_media'] = json.dumps(info, indent=None)
            self.var_engine.set_job_var('o_media', json.dumps(info, indent=None))
        except Exception:
            pass

        self.log(f'Probe complete: {fmt.get("format_name", "unknown")} '
                 f'{video_count}V {audio_count}A')
        return True


class StillsDecoder(BaseNode):
    """Stills to video conversion node."""
    node_type = 'dec_stills'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self.resolve(params.get('output', ''))

        if not output_file:
            stem = Path(input_file).stem
            output_dir = self.resolve(params.get('output_dir', ''))
            if not output_dir:
                output_dir = os.getenv('FFASTRANS_OUTPUT_DIR', 'drop_folders/output')
            output_file = str(Path(output_dir) / f'{stem}.mp4')

        if not input_file or not Path(input_file).exists():
            self.log(f'Input file not found: {input_file}')
            return False

        self.log(f'Converting stills to video: {input_file} -> {output_file}')
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        framerate = params.get('framerate', '25')
        duration = params.get('duration', '5')
        resolution = params.get('resolution', '1920x1080')
        w, h = resolution.split('x') if 'x' in resolution else ('1920', '1080')

        cmd = [FFMPEG_PATH, '-y', '-loop', '1',
               '-framerate', str(framerate),
               '-i', input_file,
               '-c:v', 'libx264', '-t', str(duration),
               '-vf', f'scale={w}:{h}',
               '-pix_fmt', 'yuv420p', output_file]

        code, _, _ = self.run_command(cmd, timeout=300)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Stills conversion complete: {output_file}')
            return True
        self.log('Stills conversion failed')
        return False


class YouTubeDecoder(BaseNode):
    """YouTube/video URL decoder - uses yt-dlp."""
    node_type = 'dec_youtube'

    def execute(self) -> bool:
        params = self.node.params
        url = self.resolve(params.get('url', self.job.input_file))

        if not url:
            self.log('No URL specified')
            return False

        output_dir = self.resolve(params.get('output_dir', ''))
        if not output_dir:
            output_dir = os.getenv('FFASTRANS_OUTPUT_DIR', 'drop_folders/output')

        self.log(f'Downloading: {url}')
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        cmd = ['yt-dlp', '-o', f'{output_dir}/%(title)s.%(ext)s',
               '--merge-output-format', 'mp4', url]

        code, stdout, stderr = self.run_command(cmd, timeout=3600)
        if code == 0 and stdout:
            for line in stdout.strip().split('\n'):
                if '[download] Destination:' in line:
                    dest = line.split('Destination:')[-1].strip()
                    if dest and Path(dest).exists():
                        self.job.variables['s_output_file'] = dest
                        self.job.input_file = dest
                        self.var_engine.set_job_var('s_output_file', dest)
                        self.log(f'Download complete: {dest}')
                        return True
            self.log('Download completed but output file not found')
            return True
        self.log(f'Download failed: {stderr}')
        return False


DECODER_NODES = {
    'dec_avmedia': MediaDecoder,
    'dec_stills': StillsDecoder,
    'dec_youtube': YouTubeDecoder,
}
