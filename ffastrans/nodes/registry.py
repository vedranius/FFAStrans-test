"""Node registry - maps node type strings to their classes."""
from .monitor_nodes import MONITOR_NODES
from .encoder_nodes import ENCODER_NODES
from .decoder_nodes import DECODER_NODES
from .filter_nodes import FILTER_NODES
from .operator_nodes import OPERATOR_NODES
from .base import BaseNode
from ..core.models import Node, Job
from ..core.variables import VariableEngine


ALL_NODES = {}
ALL_NODES.update(MONITOR_NODES)
ALL_NODES.update(ENCODER_NODES)
ALL_NODES.update(DECODER_NODES)
ALL_NODES.update(FILTER_NODES)
ALL_NODES.update(OPERATOR_NODES)

NODE_CATEGORIES = {
    'Monitors': {k: v.node_type for k, v in MONITOR_NODES.items()},
    'Decoders': {k: v.node_type for k, v in DECODER_NODES.items()},
    'Encoders': {k: v.node_type for k, v in ENCODER_NODES.items()},
    'Filters': {k: v.node_type for k, v in FILTER_NODES.items()},
    'Operators': {k: v.node_type for k, v in OPERATOR_NODES.items()},
}

NODE_DEFAULTS = {
    'mon_folder': {
        'path': '', 'accept_filter': '*.*', 'deny_filter': '',
        'create_folder': False, 'recurse': False, 'check_growing': 'once',
        'forget_missing': False, 'limit_file_size': '0',
        'rebuild_history': False, 'clear_history': False, 'poll_interval': '2',
    },
    'mon_sequence': {
        'path': '', 'pattern': '%04d', 'start': '0', 'end': '100', 'extension': 'dpx',
    },
    'dec_avmedia': {
        'input': '', 'video_decode': 'intelligent', 'audio_decode': 'intelligent',
    },
    'dec_stills': {
        'input': '', 'framerate': '25', 'duration': '5', 'resolution': '1920x1080',
    },
    'dec_youtube': {
        'url': '', 'output_dir': '',
    },
    'enc_av_mp4': {
        'input': '', 'output': '', 'vcodec': 'libx264',
        'video_bitrate': '', 'crf': '23', 'video_preset': 'medium',
        'pixel_format': 'yuv420p', 'video_profile': 'high', 'level': '4.1',
        'video_width': '', 'video_height': '', 'resize_method': 'stretch',
        'framerate': '', 'video_range': 'limited', 'faststart': True,
        'acodec': 'aac', 'audio_bitrate': '192k', 'audio_sample_rate': '48000',
    },
    'enc_av_265': {
        'input': '', 'output': '', 'vcodec': 'libx265',
        'crf': '28', 'video_preset': 'medium',
        'pixel_format': 'yuv420p', 'video_width': '', 'video_height': '',
        'resize_method': 'stretch', 'framerate': '',
        'acodec': 'aac', 'audio_bitrate': '192k',
    },
    'enc_av_prores': {
        'input': '', 'output': '', 'profile': '3',
        'pixel_format': 'yuv422p10le',
    },
    'enc_av_dnxhr': {
        'input': '', 'output': '', 'dnxhr_profile': 'DNxHR HQ',
        'pixel_format': 'yuv422p',
    },
    'enc_av_dnxhd': {
        'input': '', 'output': '', 'dnxhd_profile': 'DNxHD 185',
    },
    'enc_av_xdcamhd': {
        'input': '', 'output': '', 'video_bitrate': '50M',
    },
    'enc_av_av1': {
        'input': '', 'output': '', 'crf': '30', 'video_preset': '4',
    },
    'enc_av_customff': {
        'input': '', 'output': '', 'ffmpeg_args': '',
    },
    'enc_a_audio': {
        'input': '', 'output': '', 'acodec': 'pcm_s16le',
        'audio_sample_rate': '48000',
    },
    'avs_v_resize': {
        'input': '', 'output': '', 'width': '1920', 'height': '1080',
        'interpolation': 'lanczos',
    },
    'avs_v_crop': {
        'input': '', 'output': '', 'x': '0', 'y': '0',
        'width': '1920', 'height': '1080',
    },
    'avs_v_color': {
        'input': '', 'output': '', 'brightness': '0', 'contrast': '1',
        'saturation': '1', 'gamma': '1',
    },
    'avs_v_watermark': {
        'input': '', 'output': '', 'watermark_path': '',
        'position': 'top_right', 'opacity': '0.5',
    },
    'avs_v_tc': {
        'input': '', 'output': '', 'text': '%s_datetime%',
        'position': 'bottom_right', 'fontsize': '24', 'fontcolor': 'white',
    },
    'avs_v_deinterlace': {
        'input': '', 'output': '', 'mode': 'bob',
    },
    'avs_v_pad': {
        'input': '', 'output': '', 'width': '1920', 'height': '1080',
        'color': 'black',
    },
    'avs_v_flip': {
        'input': '', 'output': '', 'direction': 'horizontal',
    },
    'avs_v_fpsconv': {
        'input': '', 'output': '', 'target_fps': '25', 'algorithm': 'mci',
    },
    'avs_v_reverse': {
        'input': '', 'output': '',
    },
    'avs_av_fade': {
        'input': '', 'output': '', 'fade_type': 'in',
        'duration': '2', 'start': '0',
    },
    'op_cond': {
        'expressions': [],
        'dispel_on_false': False,
    },
    'op_populate': {
        'assignments': [],
    },
    'op_analyzer': {
        'input': '',
    },
    'op_foreach': {
        'variable': 's_item', 'items': '', 'delimiter': '|',
    },
    'op_hold': {
        'seconds': '5',
    },
    'cmd_run': {
        'command': '', 'timeout': '300', 'capture_output': True,
    },
    'other_email': {
        'smtp_server': '', 'smtp_port': '587', 'from': '',
        'to': '', 'subject': 'FFAStrans notification', 'body': '', 'tls': True,
    },
    'other_httpsend': {
        'url': '', 'method': 'GET', 'body': '', 'headers': {},
    },
    'other_textfile': {
        'content': '', 'output_path': '', 'mode': 'overwrite',
    },
    'dest_folder': {
        'input': '', 'path': '', 'prefix': '', 'suffix': '',
        'overwrite': True, 'unique_name': False, 'zero_padding': '0',
        'drop_original_name': False, 'drop_extension': False,
        'move_instead_of_copy': False, 'force_case': '',
    },
}


def get_node_class(node_type: str) -> type | None:
    return ALL_NODES.get(node_type)


def create_node_instance(node: Node, job: Job, var_engine: VariableEngine) -> BaseNode | None:
    cls = get_node_class(node.node_type)
    if cls is None:
        return None
    return cls(node=node, job=job, var_engine=var_engine)


def get_node_defaults(node_type: str) -> dict:
    return dict(NODE_DEFAULTS.get(node_type, {}))


def list_available_nodes() -> dict:
    result = {}
    for category, nodes in NODE_CATEGORIES.items():
        result[category] = []
        for name, ntype in nodes.items():
            result[category].append({
                'name': name,
                'type': ntype,
                'defaults': NODE_DEFAULTS.get(ntype, {}),
            })
    return result
