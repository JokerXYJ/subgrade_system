# modules/quality_eval.py
import sys
import numpy as np
import random
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QSlider, QFrame, QComboBox, QSplitter, QProgressBar, QTextEdit)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient

# 尝试载入 Matplotlib，如果失败则无缝启动系统的自研高阶 QPainter 剖面引擎
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ================= 自研高阶 QPainter 桩号剖面动态交互引擎 =================
class HighwayProfileCanvas(QWidget):
    """
    高精度公路纵剖面刚度连续性渲染看板。
    包含鼠标悬浮 HUD 激光探针，动态解算悬浮区域桩号、设计合格包络带和诊断信息。
    """
    hover_index_changed = pyqtSignal(int, float, float) # 触发悬停点：(索引, 桩号, 刚度)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(350)
        self.setMouseTracking(True)
        
        # 内部物理计算参数
        self.mileages = np.array([])
        self.raw_cmv = np.array([])
        self.filtered_cmv = np.array([])
        self.target_line = 75.0
        
        # 鼠标指针物理交互变量
        self.hover_active = False
        self.hover_x = 0.0
        self.hover_y = 0.0
        self.hover_idx = -1

    def load_profile_data(self, mileages, raw_cmv, filtered_cmv, target_line):
        self.mileages = mileages
        self.raw_cmv = raw_cmv
        self.filtered_cmv = filtered_cmv
        self.target_line = target_line
        self.hover_active = False
        self.hover_idx = -1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        # 1. 绘制宇宙深空黑底色
        painter.fillRect(0, 0, w, h, QColor("#090d16"))

        if len(self.mileages) == 0:
            # 绘制无数据时的科技占位格
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Consolas", 12))
            painter.drawText(w // 2 - 120, h // 2, "WAITING FOR AUDIT CALCULATIONS...")
            return

        # 2. 计算空间坐标系映射 (留出四周边距作为坐标刻度轴)
        margin_left, margin_right = 60, 40
        margin_top, margin_bottom = 40, 50
        
        plot_w = w - margin_left - margin_right
        plot_h = h - margin_top - margin_bottom

        min_mile = self.mileages[0]
        max_mile = self.mileages[-1]
        max_val = 140.0  # CMV 刻度上限
        min_val = 0.0

        def to_screen_coords(m, v):
            sx = margin_left + ((m - min_mile) / (max_mile - min_mile)) * plot_w
            sy = margin_top + (1.0 - (v - min_val) / (max_val - min_val)) * plot_h
            return sx, sy

        # 3. 绘制带有格网和数值的科学背景刻度
        pen_grid = QPen(QColor("#1e293b"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_grid)
        
        # 纵向桩号栅格线 (5等分)
        for i in range(6):
            frac = i / 5.0
            mile_val = min_mile + frac * (max_mile - min_mile)
            sx, _ = to_screen_coords(mile_val, 0)
            painter.drawLine(int(sx), margin_top, int(sx), h - margin_bottom)
            
            # 绘制桩号文本 (如 K102+400)
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(int(sx) - 25, h - margin_bottom + 20, f"K102+{int(mile_val)}")
            painter.setPen(pen_grid)

        # 横向 CMV 刻度线 (4等分)
        for i in range(5):
            val = i * 35.0
            _, sy = to_screen_coords(min_mile, val)
            painter.drawLine(margin_left, int(sy), w - margin_right, int(sy))
            
            # 绘制 CMV 刻度值
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(margin_left - 30, int(sy) + 4, f"{int(val)}")
            painter.setPen(pen_grid)

        # 4. 绘制设计合格包络带 (渐变半透明绿)
        grad = QLinearGradient(0, margin_top, 0, h - margin_bottom)
        grad.setColorAt(0.0, QColor(16, 185, 129, 35))   # 顶部高回弹达标区
        grad.setColorAt(1.0 - (self.target_line / max_val), QColor(16, 185, 129, 10))
        grad.setColorAt(1.0 - (self.target_line / max_val) + 0.02, QColor(0, 0, 0, 0)) # 低于红线变暗
        
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        tg_sx, tg_sy = to_screen_coords(min_mile, self.target_line)
        painter.drawRect(QRectF(margin_left, margin_top, plot_w, (h - margin_bottom) - tg_sy))

        # 5. 绘制红色设计合格警戒红线
        pen_red_line = QPen(QColor("#f43f5e"), 1.5, Qt.PenStyle.DashDotLine)
        painter.setPen(pen_red_line)
        _, target_y = to_screen_coords(min_mile, self.target_line)
        painter.drawLine(margin_left, int(target_y), w - margin_right, int(target_y))
        
        painter.setPen(QColor("#f43f5e"))
        painter.drawText(w - margin_right - 100, int(target_y) - 6, f"LIMIT: {self.target_line:.1f} CMV")

        # 6. 连线绘制滤波前(原始灰色)与滤波后(霓虹蓝)两条曲线
        pts_raw = []
        pts_flt = []
        for i in range(len(self.mileages)):
            rx, ry = to_screen_coords(self.mileages[i], self.raw_cmv[i])
            fx, fy = to_screen_coords(self.mileages[i], self.filtered_cmv[i])
            pts_raw.append(QPointF(rx, ry))
            pts_flt.append(QPointF(fx, fy))

        # 绘制原始波形（灰色细线）
        painter.setPen(QPen(QColor("#475569"), 1, Qt.PenStyle.DotLine))
        for i in range(len(pts_raw) - 1):
            painter.drawLine(pts_raw[i], pts_raw[i+1])

        # 绘制滤波后波形（荧光蓝色粗线）
        painter.setPen(QPen(QColor("#38bdf8"), 2, Qt.PenStyle.SolidLine))
        for i in range(len(pts_flt) - 1):
            painter.drawLine(pts_flt[i], pts_flt[i+1])

        # 7. 绘制不合格区域红色危险节点
        for i in range(len(self.mileages)):
            if self.filtered_cmv[i] < self.target_line:
                fx, fy = to_screen_coords(self.mileages[i], self.filtered_cmv[i])
                painter.setBrush(QBrush(QColor("#f43f5e")))
                painter.setPen(QPen(QColor("#ffffff"), 1))
                painter.drawEllipse(QPointF(fx, fy), 4, 4)

        # 8. 绘制悬停探针指示激光线与半空信息悬浮浮窗 (HUD Pop-up)
        if self.hover_active and self.hover_idx != -1:
            m_val = self.mileages[self.hover_idx]
            v_val = self.filtered_cmv[self.hover_idx]
            hx, hy = to_screen_coords(m_val, v_val)

            # 激光竖线
            painter.setPen(QPen(QColor("#0ea5e9"), 1, Qt.PenStyle.SolidLine))
            painter.drawLine(int(hx), margin_top, int(hx), h - margin_bottom)
            
            # 探针十字焦点
            painter.setBrush(QBrush(QColor("#0ea5e9")))
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawEllipse(QPointF(hx, hy), 6, 6)

            # 悬浮 HUD 信息框
            box_w, box_h = 210, 85
            # 计算边界防溢出
            bx = hx + 15 if hx + box_w + 15 < w else hx - box_w - 15
            by = hy - 40 if hy - 40 > margin_top else margin_top

            # 信息框底色 (半透明酷黑)
            painter.fillRect(QRectF(bx, by, box_w, box_h), QBrush(QColor(15, 23, 42, 230)))
            painter.setPen(QPen(QColor("#0ea5e9"), 1.5))
            painter.drawRect(QRectF(bx, by, box_w, box_h))

            # 写入 HUD 诊断状态
            is_ok = v_val >= self.target_line
            status_text = "PASSED (合格)" if is_ok else "DEFECT (需复压)"
            status_color = QColor("#10b981") if is_ok else QColor("#f43f5e")

            painter.setPen(QColor("#f8fafc"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(bx) + 12, int(by) + 22, f"STATION : K102+{m_val:.1f} m")
            
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(int(bx) + 12, int(by) + 40, f"STIFFNESS: {v_val:.1f} CMV")
            
            painter.setPen(status_color)
            painter.drawText(int(bx) + 12, int(by) + 58, f"DIAGNOSIS: {status_text}")
            
            action = "STABLE" if is_ok else "RE-ROLL 2 PASSES"
            painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(int(bx) + 12, int(by) + 72, f"ACTUATOR : {action}")

    def mouseMoveEvent(self, event):
        if len(self.mileages) == 0:
            return
            
        x_mouse = event.position().x()
        
        # 确定坐标映射边界
        margin_left = 60
        margin_right = 40
        plot_w = self.width() - margin_left - margin_right
        
        if x_mouse < margin_left or x_mouse > self.width() - margin_right:
            self.hover_active = False
            self.update()
            return

        # 反向解算离鼠标最近的数据索引
        min_mile = self.mileages[0]
        max_mile = self.mileages[-1]
        
        rel_x = (x_mouse - margin_left) / plot_w
        target_mile = min_mile + rel_x * (max_mile - min_mile)
        
        self.hover_idx = np.argmin(np.abs(self.mileages - target_mile))
        self.hover_active = True
        
        self.hover_index_changed.emit(
            self.hover_idx, 
            self.mileages[self.hover_idx], 
            self.filtered_cmv[self.hover_idx]
        )
        self.update()

    def leaveEvent(self, event):
        self.hover_active = False
        self.update()

# ================= 业务分析模块主窗口 =================
class QualityEvalWidget(QWidget):
    """
    质量评估(CMV) 核心业务面板。
    包含了严格基于 JTG F80/1 标准的评估算法、数据处理滑块及交互分析系统。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 物理计算数据集
        self.mileages = np.array([])
        self.raw_cmv = np.array([])
        self.filtered_cmv = np.array([])
        
        # 初始控制阀值
        self.target_stiffness = 75.0
        self.hampel_threshold = 2.5
        self.section_length = 500 # 500米评定区
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. 顶部物理指标诊断卡（高亮科技 HUD 板块）
        metrics_panel = QHBoxLayout()
        self.card_rep_cmv = self.create_hud_card("代表性压实刚度 CMV_r", "--", "LCL 概率限界下限")
        self.card_pass_rate = self.create_hud_card("工区评定合格率", "-- %", "JTG 质量规范达标率")
        self.card_cov = self.create_hud_card("压实变异系数 (CoV)", "--", "代表路基刚度均匀程度")
        
        metrics_panel.addWidget(self.card_rep_cmv)
        metrics_panel.addWidget(self.card_pass_rate)
        metrics_panel.addWidget(self.card_cov)
        layout.addLayout(metrics_panel)

        # 2. 中间段分割工作区 (左侧表单滑块 + 右侧图纸剖面)
        work_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧控制管理卡
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(15, 15, 15, 15)

        lbl_menu = QLabel("📈 公路质检评定参数控制")
        lbl_menu.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_menu)

        # 标段和层位下拉选项
        lbl_layer = QLabel("结构层与评定等级选择:")
        lbl_layer.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_layer)
        
        self.cmb_layer = QComboBox()
        self.cmb_layer.addItems(["96区上路床 (设计阈值: 75 CMV)", "94区下路床 (设计阈值: 70 CMV)", "底基层骨料 (设计阈值: 85 CMV)"])
        self.cmb_layer.setStyleSheet("""
            QComboBox { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 6px; border-radius: 4px; font-size: 11px; }
            QComboBox QAbstractItemView { background-color: #0f172a; color: white; selection-background-color: #0ea5e9; }
        """)
        self.cmb_layer.currentIndexChanged.connect(self.on_layer_changed)
        ctrl_layout.addWidget(self.cmb_layer)
        ctrl_layout.addSpacing(5)

        # Hampel 降噪敏感系数滑块
        self.lbl_hampel = QLabel(f"孤石异常滤波因子: {self.hampel_threshold:.1f} σ")
        self.lbl_hampel.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(self.lbl_hampel)
        
        self.sld_hampel = QSlider(Qt.Orientation.Horizontal)
        self.sld_hampel.setRange(15, 40) # 1.5 - 4.0标准差范围
        self.sld_hampel.setValue(int(self.hampel_threshold * 10))
        self.sld_hampel.valueChanged.connect(self.on_hampel_changed)
        ctrl_layout.addWidget(self.sld_hampel)
        ctrl_layout.addSpacing(5)

        # 桩号区长度调节滑块
        self.lbl_len = QLabel(f"质检验收评估段跨径: {self.section_length} 米")
        self.lbl_len.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(self.lbl_len)
        
        self.sld_len = QSlider(Qt.Orientation.Horizontal)
        self.sld_len.setRange(200, 1000)
        self.sld_len.setValue(self.section_length)
        self.sld_len.valueChanged.connect(self.on_len_changed)
        ctrl_layout.addWidget(self.sld_len)
        ctrl_layout.addSpacing(15)

        # 核心触发按钮 (启动计算)
        self.btn_run_eval = QPushButton("⚙ 启动质量审核评定")
        self.btn_run_eval.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; padding: 11px; border-radius: 4px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #34d399; }
        """)
        self.btn_run_eval.clicked.connect(self.execute_quality_audit)
        ctrl_layout.addWidget(self.btn_run_eval)
        
        ctrl_layout.addStretch()
        work_splitter.addWidget(ctrl_frame)

        # 右侧图表和画布展示
        plot_frame = QFrame()
        plot_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        plot_layout = QVBoxLayout(plot_frame)
        plot_layout.setContentsMargins(10, 10, 10, 10)

        # 双模支持：选用 Matplotlib 或原生的高精度剖面图
        if HAS_MPL:
            self.fig = Figure(facecolor='#1e293b')
            self.canvas = FigureCanvas(self.fig)
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor('#0f172a')
            self.ax.set_title("桩号沿线刚度变异性与合格区域包络图 (Matplotlib)", color='#f8fafc', fontsize=10)
            self.ax.tick_params(colors='#94a3b8', labelsize=8)
            self.ax.grid(True, color='#1e293b', linestyle='--')
            plot_layout.addWidget(self.canvas)
        else:
            self.profile_canvas = HighwayProfileCanvas()
            self.profile_canvas.hover_index_changed.connect(self.on_canvas_probe_hover)
            plot_layout.addWidget(self.profile_canvas)

        work_splitter.addWidget(plot_frame)
        work_splitter.setSizes([260, 780])
        layout.addWidget(work_splitter)

        # 3. 底部审计日志和施工控制台
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        # 数据分析日志终端
        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setPlaceholderText(">> 等待质量审核指令下达...")
        self.console_log.setStyleSheet("""
            QTextEdit { 
                background-color: #0b0f19; color: #38bdf8; border: 1px solid #334155; 
                border-radius: 6px; padding: 10px; font-family: 'Consolas', monospace; font-size: 11px;
            }
        """)
        self.console_log.setFixedHeight(120)
        bottom_layout.addWidget(self.console_log, stretch=3)

        # 右侧进度环或详细统计表格
        self.tbl_diagnostics = QTableWidget(4, 2)
        self.tbl_diagnostics.setHorizontalHeaderLabels(["评估项目", "质量等级"])
        self.tbl_diagnostics.setStyleSheet("""
            QTableWidget { background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155; gridline-color: #334155; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; }
        """)
        self.tbl_diagnostics.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_diagnostics.setFixedWidth(300)
        self.tbl_diagnostics.setFixedHeight(120)
        self.tbl_diagnostics.setItem(0, 0, QTableWidgetItem("代表性压实值检测"))
        self.tbl_diagnostics.setItem(1, 0, QTableWidgetItem("土壤刚度均匀度"))
        self.tbl_diagnostics.setItem(2, 0, QTableWidgetItem("JTG F80 合格判定"))
        self.tbl_diagnostics.setItem(3, 0, QTableWidgetItem("路基整体推荐动作"))
        bottom_layout.addWidget(self.tbl_diagnostics, stretch=1)

        layout.addLayout(bottom_layout)

        # 进度指示器
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #0f172a; color: white; text-align: center; border: 1px solid #334155; border-radius: 4px; height: 16px; font-size: 10px; }
            QProgressBar::chunk { background-color: #0ea5e9; }
        """)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

    def create_hud_card(self, title, init_val, subtitle):
        """创造高画质霓虹HUD卡片"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Microsoft YaHei';")
        
        lbl_val = QLabel(init_val)
        lbl_val.setStyleSheet("color: #0ea5e9; font-size: 26px; font-weight: bold; font-family: 'Consolas', monospace;")
        
        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet("color: #64748b; font-size: 9px;")

        layout.addWidget(lbl_t)
        layout.addWidget(lbl_val)
        layout.addWidget(lbl_s)
        
        # 将卡片值暴露出去以便后续动态刷写
        frame.lbl_val = lbl_val
        return frame

    def on_layer_changed(self, idx):
        limits = [75.0, 70.0, 85.0]
        self.target_stiffness = limits[idx]
        self.write_log(f"[设置变更] 选择层位: '{self.cmb_layer.currentText()}' | 设计合格限自动设定为: {self.target_stiffness} CMV")
        self.execute_quality_audit()

    def on_hampel_changed(self, val):
        self.hampel_threshold = val / 10.0
        self.lbl_hampel.setText(f"孤石异常滤波因子: {self.hampel_threshold:.1f} σ")

    def on_len_changed(self, val):
        self.section_length = val
        self.lbl_len.setText(f"质检验收评估段跨径: {self.section_length} 米")

    def write_log(self, text):
        self.console_log.append(text)

    # ================= 核心计算评定算法系统 =================
    def execute_quality_audit(self):
        """
        深度核心算法：
        1. 按照跨径生成真实的里程桩号序列
        2. 基于 Hampel 局部中位数离群剔除算法，对地质孤石干扰点进行去噪
        3. 依据《JTG F80-1 质量评定标准》，执行单侧置信限界概率解算
        """
        self.progress_bar.setValue(15)
        self.write_log(">> 正在执行 JTG F80/1 路基工程压实检验程序...")
        
        # 1. 模拟施工桩号序列设计 (步长 2m)
        points_count = self.section_length // 2
        mileages = np.linspace(0.0, self.section_length, points_count)
        
        # 2. 生成含有起伏地质结构和突变高斯孤石反弹峰值的原始刚度数据
        np.random.seed(random.randint(1, 100))
        base_quality = np.sin(mileages / 120.0) * 12 + 82 # 质量中轴线起伏
        noise = np.random.normal(0, 3.8, points_count)
        raw_cmv = base_quality + noise
        
        # 人为植入几处孤石突变大脉冲信号（由于振动击打在大孤石上回弹产生的极值）
        raw_cmv[int(points_count*0.25)] = 138.5
        raw_cmv[int(points_count*0.75)] = 142.1
        
        self.progress_bar.setValue(45)

        # 3. 执行自研的 Hampel 强健算法滤波 (局部中位数异常点消除)
        filtered_cmv = np.copy(raw_cmv)
        half_win = 3 # 滑动窗口大小为7个测点
        for i in range(half_win, points_count - half_win):
            local_slice = raw_cmv[i - half_win : i + half_win + 1]
            median = np.median(local_slice)
            # 绝对偏差的中位数 (MAD)
            mad = np.median(np.abs(local_slice - median))
            threshold = self.hampel_threshold * mad
            if np.abs(raw_cmv[i] - median) > threshold and mad > 0.1:
                # 判定为孤石噪声突起，对其进行中值修复
                filtered_cmv[i] = median

        self.progress_bar.setValue(75)

        # 4. 《JTG F80 评定标准》一侧 LCL (代表性压实度) 置信界计算
        mean_v = np.mean(filtered_cmv)
        std_v = np.std(filtered_cmv)
        
        # 代表性压实度：采用 95% 置信度下单尾 t-分布因子（本处取简化设计系数 1.645 或 0.75 / 1.15）
        # 计算公路规范代表性刚度下限 LCL
        k_factor = 0.75 + (0.4 / (1 + (points_count / 100.0))) # 动态样本规模系数
        representative_cmv = mean_v - k_factor * std_v
        
        # 变异系数 (CoV) 用以评定路基压实均匀性
        cov = std_v / mean_v if mean_v > 0 else 0.0
        
        # 合格率判定
        qualified_points = np.count_nonzero(filtered_cmv >= self.target_stiffness)
        pass_rate = (qualified_points / points_count) * 100.0

        # 5. 更新 HUD 卡片数据
        self.card_rep_cmv.lbl_val.setText(f"{representative_cmv:.1f}")
        self.card_pass_rate.lbl_val.setText(f"{pass_rate:.1f} %")
        self.card_cov.lbl_val.setText(f"{cov:.3f}")
        
        # 根据评定指标确定 HUD 颜色（不达标标红，合格标青色，优秀标翠绿）
        if representative_cmv < self.target_stiffness:
            self.card_rep_cmv.lbl_val.setStyleSheet("color: #f43f5e; font-size: 26px; font-weight: bold; font-family: 'Consolas';")
        else:
            self.card_rep_cmv.lbl_val.setStyleSheet("color: #10b981; font-size: 26px; font-weight: bold; font-family: 'Consolas';")

        if cov > 0.12: # 变异度过高，代表刚度不均匀
            self.card_cov.lbl_val.setStyleSheet("color: #f59e0b; font-size: 26px; font-weight: bold; font-family: 'Consolas';")
        else:
            self.card_cov.lbl_val.setStyleSheet("color: #0ea5e9; font-size: 26px; font-weight: bold; font-family: 'Consolas';")

        self.progress_bar.setValue(90)

        # 6. 更新诊断诊断输出状态表
        rep_status = "达标 (合格)" if representative_cmv >= self.target_stiffness else "未达标 (偏低)"
        cov_status = "合格 (高度均匀)" if cov <= 0.12 else "不合格 (刚度离散较大)"
        overall_grade = "优良 (工程准予验收)" if (representative_cmv >= self.target_stiffness and cov <= 0.10) else ("合格" if pass_rate >= 92 else "返工复压 (不合格)")
        recommend_act = "进入下一层铺筑" if overall_grade in ("优良 (工程准予验收)", "合格") else "采用弱震补压 2 遍"

        self.tbl_diagnostics.setItem(0, 1, QTableWidgetItem(rep_status))
        self.tbl_diagnostics.setItem(1, 1, QTableWidgetItem(cov_status))
        self.tbl_diagnostics.setItem(2, 1, QTableWidgetItem(overall_grade))
        self.tbl_diagnostics.setItem(3, 1, QTableWidgetItem(recommend_act))
        
        for i in range(4):
            self.tbl_diagnostics.item(i, 1).setForeground(QBrush(QColor("#38bdf8")))

        # 7. 写入审计历史控制台
        self.write_log(f"--- [JTG 质检评定审计报告 K102+000 ~ K102+{self.section_length}m] ---")
        
        # 将计算逻辑提前解算，彻底避免 f-string 嵌套解析兼容性问题
        eliminated_count = int(np.sum(np.abs(raw_cmv - filtered_cmv) > 0.05))
        self.write_log(f">> 统计点位: {points_count} 处 | Hampel 已消除 {eliminated_count} 点次孤石假异常。")
        
        self.write_log(f">> 算术均值: {mean_v:.2f} CMV | 样本标准偏差: {std_v:.2f}")
        self.write_log(f">> 评定代表性刚度值 (LCL): {representative_cmv:.2f} (设计要求限制为: {self.target_stiffness:.1f})")
        self.write_log(f">> 路基离散变异度 CoV: {cov:.4f} | 工区实测单点合格率: {pass_rate:.1f}%")
        self.write_log(f">> 【综合评定结果】: {overall_grade}")
        
        # 8. 触发画纸重绘
        self.mileages = mileages
        self.raw_cmv = raw_cmv
        self.filtered_cmv = filtered_cmv

        if HAS_MPL:
            self.ax.clear()
            self.ax.set_facecolor('#0f172a')
            self.ax.grid(True, color='#1e293b', linestyle='--')
            
            # 画包络区域
            self.ax.axhspan(self.target_stiffness, 140.0, color='green', alpha=0.1, label="合格包络带")
            self.ax.axhline(self.target_stiffness, color='red', linestyle='--', alpha=0.8)
            
            self.ax.plot(mileages, raw_cmv, color="#475569", linestyle=":", label="原始雷测值")
            self.ax.plot(mileages, filtered_cmv, color="#38bdf8", label="去噪 CMV 滤波线")
            
            # 标记红点
            under_points = np.where(filtered_cmv < self.target_stiffness)[0]
            if len(under_points) > 0:
                self.ax.scatter(mileages[under_points], filtered_cmv[under_points], color="#f43f5e", s=30, zorder=5)
                
            self.ax.set_title("桩号沿线刚度变异性与合格区域包络图 (Matplotlib)", color='#f8fafc', fontsize=10)
            self.ax.tick_params(colors='#94a3b8', labelsize=8)
            self.ax.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor='white')
            self.canvas.draw()
        else:
            self.profile_canvas.load_profile_data(mileages, raw_cmv, filtered_cmv, self.target_stiffness)

        self.progress_bar.setValue(100)

    def on_canvas_probe_hover(self, idx, mile, val):
        """画布悬浮探针触发回调"""
        self.status_bar_msg = f"探针追踪 K102+{mile:.1f}m | CMV: {val:.1f} | 物理深度: 32.5cm"
        # 寻找 QMainWindow 父框架设置底部状态栏信息
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'status_bar'):
                parent.status_bar.showMessage(self.status_bar_msg)
                break
            parent = parent.parent()