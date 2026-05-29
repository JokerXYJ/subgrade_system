# modules/weak_zone.py
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QHBoxLayout, QSlider, QFrame, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
from core.algorithm import CompactionEngine

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ================= 原生 2D 空间雷达散点画布 =================
class NeonSpatialCanvas(QWidget):
    """自研的高动态测点空间雷达，在缺失 matplotlib 时自动替换，渲染高科技感测点"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.xs = []
        self.ys = []
        self.vals = []
        self.anomalies = []
        self.setMinimumHeight(350)

    def load_points(self, xs, ys, vals, anomalies):
        self.xs = xs
        self.ys = ys
        self.vals = vals
        self.anomalies = anomalies
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#0b0f19"))

        # 绘制测绘基线和网格
        pen_grid = QPen(QColor("#1e293b"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_grid)
        for i in range(1, 10):
            x = int(i * w / 10)
            painter.drawLine(x, 0, x, h)
        for i in range(1, 5):
            y = int(i * h / 5)
            painter.drawLine(0, y, w, y)

        if len(self.xs) == 0:
            return

        # 映射归一化坐标并绘制点
        for i in range(len(self.xs)):
            # 桩号在 10-90m 映射到宽, 深度 5-45m 映射到高
            px = (self.xs[i] - 10) / 80 * w
            py = (self.ys[i] - 5) / 40 * h
            
            # 根据压实刚度 CMV 分配颜色
            # 刚度 >= 75 (达标) 用绿色，刚度 < 75 用黄色/红色
            stiffness = self.vals[i]
            if stiffness >= 75:
                color = QColor("#10b981") # 绿
            elif stiffness >= 65:
                color = QColor("#eab308") # 黄
            else:
                color = QColor("#f43f5e") # 橙红
                
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(px, py), 5, 5)

        # 绘制需要高亮处理的薄弱区异常报警圈
        for val in self.anomalies:
            x_anom, y_anom, _, _ = val
            px = (x_anom - 10) / 80 * w
            py = (y_anom - 5) / 40 * h
            
            # 闪烁霓虹红高亮大圈
            pen_alert = QPen(QColor("#f43f5e"), 1.8, Qt.PenStyle.SolidLine)
            painter.setPen(pen_alert)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(px, py), 12, 12)

# ================= 业务核心控制面板 =================
class WeakZoneWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.local_radius = 12.0
        self.z_threshold = -1.6
        self.generate_simulated_points()
        self.init_ui()

    def generate_simulated_points(self):
        """模拟一个 80米 * 40米 连续施工路基上的 180 个高频采集测点数据"""
        np.random.seed(99)
        self.xs = np.random.uniform(10, 90, 180)
        self.ys = np.random.uniform(5, 45, 180)
        self.vals = []
        for x, y in zip(self.xs, self.ys):
            # 人为故意埋设两处由于“弹簧土、回填漏压”产生的隐形薄弱区域
            if (30 <= x <= 45 and 20 <= y <= 35) or (70 <= x <= 85 and 10 <= y <= 22):
                self.vals.append(np.random.normal(54, 4.0)) # 未达标的 CMV
            else:
                self.vals.append(np.random.normal(83, 3.5)) # 达标的 CMV

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 1. 左侧核心空间决策控制板
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)

        lbl_panel_title = QLabel("🛡 薄弱区自动聚类决策分析")
        lbl_panel_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        left_layout.addWidget(lbl_panel_title)

        self.lbl_alert_count = QLabel("高风险测点数: 待运算")
        self.lbl_alert_count.setStyleSheet("color: #fb7185; font-size: 12px; font-weight: bold;")
        left_layout.addWidget(self.lbl_alert_count)
        left_layout.addSpacing(15)

        # 空间滑动窗邻域半径设置 (交互滑块)
        self.lbl_radius = QLabel(f"空间滑动搜索半径: {self.local_radius:.1f} 米")
        self.lbl_radius.setStyleSheet("color: #94a3b8; font-size: 11px;")
        left_layout.addWidget(self.lbl_radius)

        self.sld_radius = QSlider(Qt.Orientation.Horizontal)
        self.sld_radius.setRange(5, 25)
        self.sld_radius.setValue(int(self.local_radius))
        self.sld_radius.valueChanged.connect(self.on_radius_changed)
        left_layout.addWidget(self.sld_radius)

        # Z-score 离群强度设定 (交互滑块)
        self.lbl_z = QLabel(f"Z-score 离偏硬度指标: {self.z_threshold:.1f}")
        self.lbl_z.setStyleSheet("color: #94a3b8; font-size: 11px;")
        left_layout.addWidget(self.lbl_z)

        self.sld_z = QSlider(Qt.Orientation.Horizontal)
        self.sld_z.setRange(-25, -10) # 对应 -2.5 到 -1.0
        self.sld_z.setValue(int(self.z_threshold * 10))
        self.sld_z.valueChanged.connect(self.on_z_changed)
        left_layout.addWidget(self.sld_z)

        left_layout.addSpacing(15)

        # 交互分析执行按钮
        btn_calc = QPushButton("⚡ 执行局域偏差拟合计算")
        btn_calc.setStyleSheet("""
            QPushButton { background-color: #0284c7; color: white; padding: 12px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #0ea5e9; }
        """)
        btn_calc.clicked.connect(self.perform_spatial_clustering)
        left_layout.addWidget(btn_calc)
        
        left_layout.addSpacing(15)

        # 故障区列表输出（可删除/标记）
        self.tbl_anom = QTableWidget(0, 3)
        self.tbl_anom.setHorizontalHeaderLabels(["桩号 X", "偏幅 Y", "CMV 刚度"])
        self.tbl_anom.setStyleSheet("""
            QTableWidget { background-color: #0f172a; color: #f1f5f9; border: 1px solid #334155; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; }
        """)
        self.tbl_anom.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.tbl_anom)

        layout.addWidget(left_panel, stretch=1)

        # 2. 右侧高灵敏雷达测绘板
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        self.right_layout = QVBoxLayout(self.right_panel)

        if HAS_MPL:
            self.fig = Figure(facecolor='#1e293b')
            self.canvas = FigureCanvas(self.fig)
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor('#0f172a')
            self.ax.set_title("连续式车载扫描点位与压实薄弱区分布 (Matplotlib)", color='#f8fafc', fontsize=11)
            self.ax.tick_params(colors='#94a3b8', labelsize=8)
            self.ax.grid(True, color='#1e293b', linestyle='--')
            self.right_layout.addWidget(self.canvas)
        else:
            self.neon_canvas = NeonSpatialCanvas()
            self.right_layout.addWidget(self.neon_canvas)

        layout.addWidget(self.right_panel, stretch=2.2)
        
        # 启动时执行初次解算
        self.perform_spatial_clustering()

    def on_radius_changed(self, val):
        self.local_radius = float(val)
        self.lbl_radius.setText(f"空间滑动搜索半径: {self.local_radius:.1f} 米")
        self.perform_spatial_clustering()

    def on_z_changed(self, val):
        self.z_threshold = float(val) / 10.0
        self.lbl_z.setText(f"Z-score 离偏度指标: {self.z_threshold:.1f}")
        self.perform_spatial_clustering()

    def perform_spatial_clustering(self):
        # 封装底层算法库格式
        points = [(self.xs[i], self.ys[i], self.vals[i], i) for i in range(len(self.xs))]
        
        # 执行滑动 Z-score 计算
        anomalies = CompactionEngine.detect_weak_zones(points, self.local_radius, self.z_threshold)
        self.lbl_alert_count.setText(f"高风险预警点数量: {len(anomalies)} 个")

        # 刷新诊断表
        self.tbl_anom.setRowCount(0)
        for r_idx, (ax_x, ax_y, val, _) in enumerate(anomalies[:12]): # 表中最多显示前12条严重记录
            self.tbl_anom.insertRow(r_idx)
            self.tbl_anom.setItem(r_idx, 0, QTableWidgetItem(f"K102+{ax_x:.1f}m"))
            self.tbl_anom.setItem(r_idx, 1, QTableWidgetItem(f"{ax_y:.1f}m"))
            self.tbl_anom.setItem(r_idx, 2, QTableWidgetItem(f"{val:.1f}"))

        # 重绘绘图层
        if HAS_MPL:
            self.ax.clear()
            self.ax.set_facecolor('#0f172a')
            self.ax.grid(True, color='#1e293b', linestyle='--')
            
            # 根据压实度分级填充散点颜色
            self.ax.scatter(self.xs, self.ys, c=self.vals, cmap="RdYlGn", s=35, label="扫描状态点")
            
            # 画出警示环
            if anomalies:
                ax_x = [p[0] for p in anomalies]
                ax_y = [p[1] for p in anomalies]
                self.ax.scatter(ax_x, ax_y, facecolors='none', edgecolors='#ef4444', s=100, linewidths=1.5, label="极低异常点")
                
            self.ax.set_title("连续式车载扫描点位与压实薄弱区分布 (Matplotlib)", color='#f8fafc', fontsize=11)
            self.ax.tick_params(colors='#94a3b8', labelsize=8)
            self.canvas.draw()
        else:
            self.neon_canvas.load_points(self.xs, self.ys, self.vals, anomalies)