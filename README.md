# 雷达健康监测系统 · 公开演示版

基于 Vue 3、Vite、Element Plus、Electron、Flask 和 Socket.IO 的健康监测演示工程，包含工业 HMI 导航、健康总览、数据处理、分层故障诊断、轴承部件诊断、历史记录及算法管理界面。

## 公开范围

本仓库是独立的公开展示副本。所有演示测点、取值范围、拓扑和时序值均由自定义配置与合成公式生成，不是设备实测数据。轴承页面使用本地示例规则进行健康度和候选原因判别；其置信度和排序分数仅用于界面演示，不代表经过实测验证的概率或诊断准确率。

客户协议、协议解码器、原始收发日志、真实参数字典、客户连接关系图、衍生训练数据、内部文档、模型权重及携带受限数据的旧安装包均未公开。完整私有工程另行保管。公开仓库采用新提交历史，不包含私有工程的旧提交。

## 运行

先准备 Python 3.12+ 与 Node.js 20+。

```bash
python -m venv backend/.venv
# Windows 使用 backend/.venv/Scripts/python.exe；Linux/macOS 使用 backend/.venv/bin/python
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe backend/run.py
```

另开一个终端启动前端：

```bash
cd frontend
npm ci
python ../config/build_params.py
npm run dev
```

访问 http://127.0.0.1:5173/bearing-diagnosis 查看轴承演示。后端默认绑定 127.0.0.1:5000；所有默认地址均为本机回环地址。

```bash
cd frontend
npm run build
```

模型管理中的 K-Means、SOM 和轻量 MLP 使用确定的合成训练样本；模型输出仅演示软件链路。依赖私有数据和权重的 GAT/重构实验不包含可复现的实测结果，公开版将明确报告资源不可用。请勿把演示值或演示指标作为真实设备性能结论。

## 桌面构建

```bash
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-desktop.txt
cd frontend
npm run desktop:build:win
```

公开版不提供此前的 Windows 安装包，因为旧安装包内含受限数据。这里的打包配置只包含公开版源码、自定义配置及本机新生成的后端构建产物。

## 数据与扩展

`config/params.json` 是前后端共享的演示参数源，`config/build_params.py` 只从该文件生成前端配置。演示状态阈值为：60 及以上正常，30 至小于 60 故障，低于 30 报废。专有协议适配器不在公开版本中，可在获授权的私有环境实现，不应把日志、密钥或客户材料提交到公开仓库。
