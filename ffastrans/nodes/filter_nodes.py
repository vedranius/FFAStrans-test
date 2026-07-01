"""Video/audio filter nodes using FFmpeg filters.

Matches original FFAStrans filter nodes (translated from AviSynth+ to FFmpeg):
- avs_v_resize: Video resize
- avs_v_crop: Video crop
- avs_v_color: Color correction
- avs_v_watermark: Watermark overlay
- avs_v_tc: Timecode burn-in
- avs_v_deinterlace: Deinterlace
- avs_v_pad: Add padding
- avs_v_flip: Flip
- avs_v_fpsconv: Frame rate conversion
- avs_v_reverse: Reverse video
- avs_av_fade: Audio/video fade
"""
import os
import logging
from .base import BaseNode
from ..core.config import FFMPEG_PATH

logger = logging.getLogger('ffastrans.nodes.filter')


class BaseFilter(BaseNode):
    def _apply_filter(self, vf_filter: str, extra_inputs: list = None) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self.resolve(params.get('output', ''))

        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            ext = Path(input_file).suffix
            output_file = str(Path(input_file).parent / f'{stem}_filtered{ext}')

        cmd = [FFMPEG_PATH, '-y']
        if extra_inputs:
            for ei in extra_inputs:
                cmd.extend(['-i', ei])
        else:
            cmd.extend(['-i', input_file])
        cmd.extend(['-vf', vf_filter])
        cmd.extend(['-map', '0:v?', '-map', '0:a?'])
        cmd.append(output_file)

        self.log(f'Applying filter: {vf_filter}')
        code, _, _ = self.run_command(cmd, timeout=3600)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.job.input_file = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Filter applied: {output_file}')
            return True
        self.log('Filter failed')
        return False


class ResizeFilter(BaseFilter):
    """Video resize filter."""
    node_type = 'avs_v_resize'

    def execute(self) -> bool:
        w = self.node.params.get('width', '1920')
        h = self.node.params.get('height', '1080')
        interp = self.node.params.get('interpolation', 'lanczos')
        vf = f'scale={w}:{h}:flags={interp}'
        return self._apply_filter(vf)


class CropFilter(BaseFilter):
    """Video crop filter."""
    node_type = 'avs_v_crop'

    def execute(self) -> bool:
        x = self.node.params.get('x', '0')
        y = self.node.params.get('y', '0')
        w = self.node.params.get('width', '1920')
        h = self.node.params.get('height', '1080')
        vf = f'crop={w}:{h}:{x}:{y}'
        return self._apply_filter(vf)


class ColorFilter(BaseFilter):
    """Color correction filter."""
    node_type = 'avs_v_color'

    def execute(self) -> bool:
        brightness = self.node.params.get('brightness', '0')
        contrast = self.node.params.get('contrast', '1')
        saturation = self.node.params.get('saturation', '1')
        gamma = self.node.params.get('gamma', '1')
        vf = f'eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma}'
        return self._apply_filter(vf)


class WatermarkFilter(BaseFilter):
    """Watermark overlay filter."""
    node_type = 'avs_v_watermark'

    def execute(self) -> bool:
        watermark = self.resolve(self.node.params.get('watermark_path', ''))
        position = self.node.params.get('position', 'top_right')
        opacity = self.node.params.get('opacity', '0.5')

        pos_map = {
            'top_left': '10:10',
            'top_right': 'main_w-overlay_w-10:10',
            'bottom_left': '10:main_h-overlay_h-10',
            'bottom_right': 'main_w-overlay_w-10:main_h-overlay_h-10',
            'center': '(main_w-overlay_w)/2:(main_h-overlay_h)/2',
        }
        pos = pos_map.get(position, pos_map['top_right'])

        vf = f'overlay={pos}:format=auto'
        return self._apply_filter(vf, extra_inputs=[watermark])


class TimecodeFilter(BaseFilter):
    """Timecode burn-in filter."""
    node_type = 'avs_v_tc'

    def execute(self) -> bool:
        tc_text = self.resolve(self.node.params.get('text', '%s_datetime%'))
        position = self.node.params.get('position', 'bottom_right')
        fontsize = self.node.params.get('fontsize', '24')
        fontcolor = self.node.params.get('fontcolor', 'white')
        fontfile = self.node.params.get('fontfile', '')

        pos_map = {
            'top_left': '10:10',
            'top_right': 'w-tw-10:10',
            'bottom_left': '10:h-th-10',
            'bottom_right': 'w-tw-10:h-th-10',
        }
        pos = pos_map.get(position, pos_map['bottom_right'])

        escaped_text = tc_text.replace("'", "\\'").replace(":", "\\:")
        vf = f"drawtext=text='{escaped_text}':fontsize={fontsize}:fontcolor={fontcolor}:x={pos}"
        if fontfile:
            vf += f':fontfile={fontfile}'
        return self._apply_filter(vf)


class DeinterlaceFilter(BaseFilter):
    """Deinterlace filter."""
    node_type = 'avs_v_deinterlace'

    def execute(self) -> bool:
        mode = self.node.params.get('mode', 'bob')
        if mode == 'bob':
            vf = 'yadif=0:-1:0'
        elif mode == 'weave':
            vf = 'yadif=1:-1:0'
        else:
            vf = 'yadif=0:-1:0'
        return self._apply_filter(vf)


class PadFilter(BaseFilter):
    """Add padding filter."""
    node_type = 'avs_v_pad'

    def execute(self) -> bool:
        w = self.node.params.get('width', '1920')
        h = self.node.params.get('height', '1080')
        color = self.node.params.get('color', 'black')
        vf = f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={color}'
        return self._apply_filter(vf)


class FlipFilter(BaseFilter):
    """Flip filter."""
    node_type = 'avs_v_flip'

    def execute(self) -> bool:
        direction = self.node.params.get('direction', 'horizontal')
        vf = 'hflip' if direction == 'horizontal' else 'vflip'
        return self._apply_filter(vf)


class FPSFilter(BaseFilter):
    """Frame rate conversion filter."""
    node_type = 'avs_v_fpsconv'

    def execute(self) -> bool:
        target_fps = self.node.params.get('target_fps', '25')
        algo = self.node.params.get('algorithm', 'mci')
        if algo == 'mci':
            vf = f'minterpolate=fps={target_fps}:mi_mode=mci'
        elif algo == 'blend':
            vf = f'minterpolate=fps={target_fps}:mi_mode=blend'
        else:
            vf = f'fps={target_fps}'
        return self._apply_filter(vf)


class ReverseFilter(BaseFilter):
    """Reverse video filter."""
    node_type = 'avs_v_reverse'

    def execute(self) -> bool:
        vf = 'reverse'
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self.resolve(params.get('output', ''))
        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(input_file).parent / f'{stem}_reversed{Path(input_file).suffix}')
        cmd = [FFMPEG_PATH, '-y', '-i', input_file, '-vf', vf, '-af', 'areverse', output_file]
        self.log('Reversing video')
        code, _, _ = self.run_command(cmd, timeout=3600)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.job.input_file = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Reverse complete: {output_file}')
            return True
        self.log('Reverse failed')
        return False


class FadeFilter(BaseFilter):
    """Audio/video fade filter."""
    node_type = 'avs_av_fade'

    def execute(self) -> bool:
        fade_type = self.node.params.get('fade_type', 'in')
        duration = self.node.params.get('duration', '2')
        start = self.node.params.get('start', '0')

        if fade_type == 'in':
            vf = f'fade=t=in:st={start}:d={duration}'
            af = f'afade=t=in:st={start}:d={duration}'
        else:
            vf = f'fade=t=out:st={start}:d={duration}'
            af = f'afade=t=out:st={start}:d={duration}'

        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_file = self.resolve(params.get('output', ''))
        if not output_file:
            from pathlib import Path
            stem = Path(input_file).stem
            output_file = str(Path(input_file).parent / f'{stem}_fade{Path(input_file).suffix}')

        cmd = [FFMPEG_PATH, '-y', '-i', input_file, '-vf', vf, '-af', af, output_file]
        self.log(f'Applying fade {fade_type}')
        code, _, _ = self.run_command(cmd, timeout=3600)
        if code == 0:
            self.job.variables['s_output_file'] = output_file
            self.job.input_file = output_file
            self.var_engine.set_job_var('s_output_file', output_file)
            self.log(f'Fade applied: {output_file}')
            return True
        self.log('Fade failed')
        return False


FILTER_NODES = {
    'avs_v_resize': ResizeFilter,
    'avs_v_crop': CropFilter,
    'avs_v_color': ColorFilter,
    'avs_v_watermark': WatermarkFilter,
    'avs_v_tc': TimecodeFilter,
    'avs_v_deinterlace': DeinterlaceFilter,
    'avs_v_pad': PadFilter,
    'avs_v_flip': FlipFilter,
    'avs_v_fpsconv': FPSFilter,
    'avs_v_reverse': ReverseFilter,
    'avs_av_fade': FadeFilter,
}
