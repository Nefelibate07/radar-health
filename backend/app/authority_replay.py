"""合成演示快照源。兼容工程接口名称，但不读取任何真实协议或日志。"""
import math
import threading
from datetime import datetime
from .subsystems import SUBSYSTEMS

class DemoReplay:
    def __init__(self):
        self._index = 0
        self._lock = threading.RLock()
    @property
    def enabled(self):
        return True
    def next(self):
        with self._lock:
            self._index += 1
            values = {}
            for subsystem in SUBSYSTEMS:
                for parameter in subsystem['params']:
                    base = parameter['demo_baseline']
                    values[parameter['id']] = round(base * (1 + 0.02 * math.sin(self._index * 0.3)), 3)
            stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return {'values':values,'source_type':'synthetic_demo','source_file':None,'source_line_no':None,'raw_timestamp':stamp,'decoded_timestamp':stamp,'sequence':self._index,'unit_count':len(SUBSYSTEMS),'decode_issues':[],'protocol_status':[]}
    def status(self):
        return {'enabled':True,'source_type':'synthetic_demo','next_row':self._index,'row_count':0,'source_file_count':0,'source_files':[],'loop':True,'note':'所有值由公开演示公式生成，不是设备实测记录。'}
    def reset(self):
        with self._lock:
            self._index = 0

AUTHORITY_REPLAY = DemoReplay()
AUTHORITY_UNIT_HEALTH_SCOPE = {}
AUTHORITY_SCORE_UNMAPPED_STATUS = False
