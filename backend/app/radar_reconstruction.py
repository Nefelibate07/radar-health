"""公开版不分发依赖客户参数映射、训练数据及模型权重的专用重构实现。"""
GAT_RECONSTRUCTION = 'gat_vae_reconstruction'
_MESSAGE = '公开演示版未提供私有重构模型、参数映射或实测训练数据。'

def runtime_status():
    return {'available': False, 'trained': False, 'source_type': 'synthetic_demo', 'message': _MESSAGE}

def evaluate_live_snapshot(*args, **kwargs):
    raise ValueError(_MESSAGE)

def reconstruction_demo(*args, **kwargs):
    raise ValueError(_MESSAGE)
