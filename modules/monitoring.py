# modules/monitoring.py
import numpy as np
import random
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont

# 尝试导入 Matplotlib，如果失败则启用系统自研的原生 QPainter 矢量示波器
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ================= 核心计算线程 =================
class SensorAcquisitionThread(QThread):
    """高频传感器物理信号采集与 FFT 实时变换线程"""
    data_emitted = pyqtSignal(np.ndarray, float, float, float) # 信号数组, 频率, 振幅, CMV

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.speed = 3.0
        self.moisture = 1.0

    def run(self):
        self.running = True
        sampling_rate = 200 # 200Hz 采样
        n_samples = 200

        while self.running:
            self.msleep(100) # 10Hz 屏幕刷新率
            t = np.linspace(0, 1, n_samples)
            
            # 土壤刚度反馈模型 (含水量越高，刚度越低，二次谐波能量损耗越严重)
            stiffness_ratio = np.clip(2.2 - self.moisture, 0.4, 2.0)
            
            # 模拟偏心振动压路机激振基波 (32Hz)
            f_wave = 1.4 * stiffness_ratio * np.sin(2 * np.pi * 32 * t)
            # 模拟骨料连锁反弹产生的二次谐波 (64Hz)
            h_wave = 0.25 * (self.speed / 3.0) * np.sin(2 * np.pi * 64 * t)
            # 引入路基不均匀介质噪声
            noise = np.random.normal(0, 0.15, n_samples)
            
            combined_signal = f_wave + h_wave + noise
            
            # FFT 快速傅里叶频谱分析提取
            fft_vals = np.abs(np.fft.rfft(combined_signal))
            amp_f = float(fft_vals[32])
            amp_h = float(fft_vals[64])
            
            # CMV 计算公式
            cmv = 300.0 * (amp_h / amp_f) if amp_f > 0 else 0.0
            cmv = np.clip(cmv, 0.0, 150.0)

            self.data_emitted.emit(combined_signal, 32.0, amp_f, cmv)

# ================= 原生矢量示波器 Fallback =================
class NeonVectorScope(QWidget):
    """自研原生高帧率矢量示波网格，用于在无 matplotlib 时提供高性能展示"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = np.zeros(200)
        self.cmv_val = 0.0
        self.setMinimumHeight(280)

    def update_data(self, data, cmv):
        self.points = data
        self.cmv_val = cmv
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. 绘制暗色星空背景
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#0b0f19"))

        # 2. 绘制高科技示波器绿色网格线
        pen_grid = QPen(QColor("#1e293b"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_grid)
        cols, rows = 10, 6
        for i in range(1, cols):
            x = int(i * w / cols)
            painter.drawLine(x, 0, x, h)
        for i in range(1, rows):
            y = int(i * h / rows)
            painter.drawLine(0, y, w, y)

        # 3. 绘制零电平参考线 (霓虹红)
        painter.setPen(QPen(QColor("#f43f5e"), 1, Qt.PenStyle.SolidLine))
        painter.drawLine(0, int(h/2), w, int(h/2))

        # 4. 动态绘制信号曲线 (荧光青色)
        if len(self.points) > 0:
            pen_signal = QPen(QColor("#0ea5e9"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen_signal)
            
            max_y = 3.0 # 幅值归一化映射
            pts = []
            for idx, val in enumerate(self.points):
                x_pos = idx * w / len(self.points)
                y_pos = h/2 - (val / max_y) * (h/2)
                pts.append(QPointF(x_pos, y_pos))
                
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i+1])

        # 5. 右上角绘制实时动态 HUD 字符
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(w - 180, 25, f"TELEMETRY: ACTIVE")
        painter.drawText(w - 180, 45, f"CMV EVAL: {self.cmv_val:.1f}")

# ================= 主控制窗口 =================
class RealtimeMonitorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = SensorAcquisitionThread(self)
        self.thread.data_emitted.connect(self.handle_telemetry)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 1. 左侧硬核交互控制面板
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)

        self.btn_toggle = QPushButton("▶ 启动高频传感器链路")
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #10b981; color: white; border: none; 
                border-radius: 4px; padding: 12px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #34d399; }
        """)
        self.btn_toggle.clicked.connect(self.toggle_sensor_capture)
        left_layout.addWidget(self.btn_toggle)
        left_layout.addSpacing(10)

        # 实时交互旋钮/滑块组
        lbl_speed = QLabel("机具行进时速动态设定 (km/h):")
        lbl_speed.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(lbl_speed)
        
        self.sld_speed = QSlider(Qt.Orientation.Horizontal)
        self.sld_speed.setRange(10, 60) # 1.0 - 6.0 km/h
        self.sld_speed.setValue(30)
        self.sld_speed.valueChanged.connect(self.on_speed_changed)
        left_layout.addWidget(self.sld_speed)

        lbl_moisture = QLabel("填料含水率因子 (阻尼调节):")
        lbl_moisture.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(lbl_moisture)
        
        self.sld_moisture = QSlider(Qt.Orientation.Horizontal)
        self.sld_moisture.setRange(50, 150)
        self.sld_moisture.setValue(100)
        self.sld_moisture.valueChanged.connect(self.on_moisture_changed)
        left_layout.addWidget(self.sld_moisture)
        left_layout.addSpacing(15)

        # 数据状态列表
        self.tbl_status = QTableWidget(5, 2)
        self.tbl_status.setHorizontalHeaderLabels(["诊断参量", "高频物理读数"])
        self.tbl_status.setStyleSheet("""
            QTableWidget { background-color: #0f172a; color: #f1f5f9; border: 1px solid #334155; gridline-color: #1e293b; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; }
        """)
        self.tbl_status.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_status.setItem(0, 0, QTableWidgetItem("车辆前进速度"))
        self.tbl_status.setItem(1, 0, QTableWidgetItem("轴心垂直振频"))
        self.tbl_status.setItem(2, 0, QTableWidgetItem("基波幅值 A_w"))
        self.tbl_status.setItem(3, 0, QTableWidgetItem("土壤刚度系数"))
        self.tbl_status.setItem(4, 0, QTableWidgetItem("瞬态测定 CMV"))
        left_layout.addWidget(self.tbl_status)

        layout.addWidget(left_panel, stretch=1)

        # 2. 右侧高动态渲染看板
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        self.right_layout = QVBoxLayout(self.right_panel)

        if HAS_MPL:
            # 皮肤深度定制的 Matplotlib 图表
            self.fig = Figure(facecolor='#1e293b')
            self.canvas = FigureCanvas(self.fig)
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor('#0f172a')
            self.ax.set_title("高频加速度传感器动力学响应波形 (Matplotlib)", color='#f8fafc', fontsize=11, pad=10)
            self.ax.tick_params(colors='#94a3b8', labelsize=8)
            self.ax.grid(True, color='#1e293b', linestyle='--')
            self.line, = self.ax.plot(np.zeros(200), color="#0ea5e9", linewidth=1.5)
            self.right_layout.addWidget(self.canvas)
        else:
            # 启用备用自研矢量示波器
            self.neon_scope = NeonVectorScope()
            self.right_layout.addWidget(self.neon_scope)

        layout.addWidget(self.right_panel, stretch=2)

    def toggle_sensor_capture(self):
        if not self.thread.running:
            self.thread.start()
            self.btn_toggle.setText("⏸ 挂起高频数据网关")
            self.btn_toggle.setStyleSheet("background-color: #ef4444; color: white; border-radius: 4px; padding: 12px; font-weight: bold;")
        else:
            self.thread.running = False
            self.thread.wait()
            self.btn_toggle.setText("▶ 启动高频传感器链路")
            self.btn_toggle.setStyleSheet("background-color: #10b981; color: white; border-radius: 4px; padding: 12px; font-weight: bold;")

    def on_speed_changed(self, val):
        self.thread.speed = val / 10.0

    def on_moisture_changed(self, val):
        self.thread.moisture = val / 100.0

    def handle_telemetry(self, signal, freq, amp_f, cmv):
        # 刷新表格数据并设定红绿警示颜色
        self.tbl_status.setItem(0, 1, QTableWidgetItem(f"{self.thread.speed:.2f} km/h"))
        self.tbl_status.setItem(1, 1, QTableWidgetItem(f"{freq:.1f} Hz"))
        self.tbl_status.setItem(2, 1, QTableWidgetItem(f"{amp_f:.3f} g"))
        self.tbl_status.setItem(3, 1, QTableWidgetItem(f"{1.0 / self.thread.moisture:.2f}"))
        
        item_cmv = QTableWidgetItem(f"{cmv:.1f}")
        if cmv >= 75:
            item_cmv.setForeground(QBrush(QColor("#10b981"))) # 达标绿色
        else:
            item_cmv.setForeground(QBrush(QColor("#f43f5e"))) # 未达标红色
        self.tbl_status.setItem(4, 1, item_cmv)

        # 刷新示波器显示
        if HAS_MPL:
            self.line.set_ydata(signal)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw()
        else:
            self.neon_scope.update_data(signal, cmv)

    def closeEvent(self, event):
        self.thread.running = False
        self.thread.wait()
        super().closeEvent(event)