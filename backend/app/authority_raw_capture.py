"""公开版不包含客户原始协议解码器。通用 JSONL 接入仍由 file_capture 支持。"""
class RawCaptureSkip(ValueError):
    def __init__(self, code, detail=None):
        self.code = code
        super().__init__(detail or code)

def decoder_status():
    return {'available':False,'source_type':'synthetic_demo','note':'客户专用协议解码器未包含在公开版。'}

def decode_authority_raw_line(*args, **kwargs):
    raise RawCaptureSkip('private_adapter_not_distributed', '公开版仅支持合成演示或通用 JSONL 数据。')
