# modules/pass_count.py
import numpy as np
import random
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QSplitter, QSlider, QComboBox, 
                             QTextEdit, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient

# ================= 1. 自研原生高频矢量直方图 =================
class NeonPassCountHistogram(QWidget):
    """自研的原生压实遍数频数分布直方图，提供超流畅的暗色霓虹数据可视化"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frequencies = np.zeros(8) # 0 到 7+ 遍的占比
        self.setMinimumHeight(150)

    def update_frequencies(self, grid_data):
        total = grid_data.size
        for i in range(8):
            if i < 7:
                self.frequencies[i] = np.count_nonzero(grid_data == i) / total * 100.0
            else:
                self.frequencies[i] = np.count_nonzero(grid_data >= i) / total * 100.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#0f172a")) # 深色底色

        margin_l, margin_r = 40, 20
        margin_t, margin_b = 25, 25
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b

        # 绘制背景横向虚线
        pen_line = QPen(QColor("#1e293b"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_line)
        for i in range(4):
            val_y = margin_t + (i / 3.0) * plot_h
            painter.drawLine(margin_l, int(val_y), w - margin_r, int(val_y))

        # 绘制 8 个柱状图条 (带渐变霓虹色)
        if len(self.frequencies) == 0:
            return

        bar_w = (plot_w / 8) * 0.6
        gap = (plot_w / 8) * 0.4
        max_freq = max(max(self.frequencies), 10.0) # 刻度上限

        # 颜色映射组
        colors = [
            QColor("#475569"), QColor("#ea580c"), QColor("#d97706"),
            QColor("#ca8a04"), QColor("#16a34a"), QColor("#15803d"),
            QColor("#166534"), QColor("#6b21a8")
        ]

        for i in range(8):
            freq = self.frequencies[i]
            bar_h = (freq / max_freq) * plot_h
            bx = margin_l + i * (bar_w + gap) + gap / 2
            by = h - margin_b - bar_h

            # 创建霓虹渐变笔刷
            grad = QLinearGradient(bx, by, bx, h - margin_b)
            grad.setColorAt(0.0, colors[i])
            grad.setColorAt(1.0, QColor(colors[i].red(), colors[i].green(), colors[i].blue(), 50))

            painter.fillRect(QRectF(bx, by, bar_w, bar_h), QBrush(grad))
            
            # 画一个细亮边框
            painter.setPen(QPen(colors[i], 1))
            painter.drawRect(QRectF(bx, by, bar_w, bar_h))

            # 底部标注遍数
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            text = f"{i}P" if i < 7 else "7P+"
            painter.drawText(int(bx + bar_w/2 - 10), h - 8, text)

            # 柱子上方写数值 %
            if freq > 0:
                painter.setPen(QColor("#94a3b8"))
                painter.drawText(int(bx + bar_w/2 - 12), int(by - 5), f"{freq:.0f}%")

# ================= 2. 核心 2D 物理轨迹网格看板 =================
class NeonPassCountGrid(QWidget):
    """
    自研的二维路面连续碾压网格图纸。
    具备拖拽涂抹、车辆越界检测、鼠标悬浮雷达十字线。
    """
    inspect_cell_hovered = pyqtSignal(int, int, int) # 桩号, 横宽, 遍数

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = 40 # 横向 40米
        self.cols = 100 # 纵向 100米
        self.matrix = np.zeros((self.rows, self.cols), dtype=int)
        self.setMinimumHeight(380)
        self.setMouseTracking(True)
        
        # 拖动绘制辅助变量
        self.is_drawing = False
        self.draw_brush_radius = 2

        # 悬浮指示辅助
        self.hover_active = False
        self.hover_col = -1
        self.hover_row = -1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cell_w = w / self.cols
        cell_h = h / self.rows

        # 压实遍数对应的科技渐变色映射
        color_map = {
            0: QColor("#0f172a"), # 没压过：极黑
            1: QColor("#451a03"), # 1遍
            2: QColor("#7c2d12"), # 2遍
            3: QColor("#b45309"), # 3遍
            4: QColor("#15803d"), # 4遍 (达标下限)
            5: QColor("#166534"), # 5遍 (黄金刚度区)
            6: QColor("#14532d"), # 6遍 (完美合格区)
            7: QColor("#581c87"), # 7遍 (过度压实警告区)
        }

        # 1. 栅格着色渲染
        for r in range(self.rows):
            for c in range(self.cols):
                val = self.matrix[r, c]
                color = color_map.get(val, QColor("#3b0764")) if val < 7 else color_map[7]
                rect = QRectF(c * cell_w, r * cell_h, cell_w - 0.3, cell_h - 0.3)
                painter.fillRect(rect, QBrush(color))

        # 2. 绘制网格辅助边界标线 (每 10 米一道高亮细线)
        painter.setPen(QPen(QColor("#1e293b"), 0.5))
        for i in range(1, 10):
            cx = int(i * w / 10)
            painter.drawLine(cx, 0, cx, h)

        # 3. 绘制鼠标雷达扫描探针
        if self.hover_active and 0 <= self.hover_col < self.cols and 0 <= self.hover_row < self.rows:
            hx = self.hover_col * cell_w + cell_w/2
            hy = self.hover_row * cell_h + cell_h/2

            # 十字定位线 (霓虹青)
            pen_probe = QPen(QColor("#0ea5e9"), 1, Qt.PenStyle.DashDotLine)
            painter.setPen(pen_probe)
            painter.drawLine(0, int(hy), w, int(hy))
            painter.drawLine(int(hx), 0, int(hx), h)

            # 焦点选中发光圆
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QBrush(QColor(14, 165, 233, 100)))
            painter.drawEllipse(QPointF(hx, hy), 7, 7)

            # 悬浮迷你 HUD
            hud_w, hud_h = 160, 65
            bx = hx + 15 if hx + hud_w + 15 < w else hx - hud_w - 15
            by = hy - 15 if hy - hud_h - 15 > 0 else hy + 15

            painter.fillRect(QRectF(bx, by, hud_w, hud_h), QBrush(QColor(15, 23, 42, 230)))
            painter.setPen(QPen(QColor("#38bdf8"), 1))
            painter.drawRect(QRectF(bx, by, hud_w, hud_h))

            # 绘制 HUD 内文本
            cur_passes = self.matrix[self.hover_row, self.hover_col]
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(bx + 10), int(by + 18), f"COORD : K102+{self.hover_col}m")
            painter.drawText(int(bx + 10), int(by + 34), f"WIDTH : {self.hover_row} m")
            
            status_text = "NORMAL" if cur_passes < 7 else "OVER-COMPACT"
            status_color = QColor("#38bdf8") if cur_passes < 7 else QColor("#ef4444")
            painter.setPen(status_color)
            painter.drawText(int(bx + 10), int(by + 50), f"PASSES: {cur_passes}P [{status_text}]")

    # ================= 鼠标拖拽涂抹物理支持（手动碾压驾驶模式） =================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.paint_track_point(event.position())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False

    def mouseMoveEvent(self, event):
        w, h = self.width(), self.height()
        cell_w = w / self.cols
        cell_h = h / self.rows
        
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)

        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.hover_active = True
            self.hover_col = col
            self.hover_row = row
            self.inspect_cell_hovered.emit(col, row, int(self.matrix[row, col]))
        else:
            self.hover_active = False

        if self.is_drawing:
            self.paint_track_point(event.position())
        else:
            self.update()

    def leaveEvent(self, event):
        self.hover_active = False
        self.update()

    def paint_track_point(self, pos):
        """鼠标拖动，手动给填料路基施加能量碾压"""
        w, h = self.width(), self.height()
        cell_w = w / self.cols
        cell_h = h / self.rows
        
        center_col = int(pos.x() / cell_w)
        center_row = int(pos.y() / cell_h)
        
        rad = self.draw_brush_radius
        for r in range(center_row - rad, center_row + rad + 1):
            for c in range(center_col - rad, center_col + rad + 1):
                if 0 <= r < self.rows and 0 <= c < self.cols:
                    # 模拟叠轮压实
                    self.matrix[r, c] = min(self.matrix[r, c] + 1, 10)
        self.update()

# ================= 3. 压实遍数分析大控制台 =================
class PassCountWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 物理控制引擎
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.advance_simulated_vehicle)
        self.vehicle_x = 0
        self.vehicle_direction = 1 # 1: 前进, -1: 后退
        self.sim_lane = 2
        
        # 碾压动力学预设
        self.drum_width = 6
        self.steering_drift = 0
        self.auto_rolling_mode = "Parallel Overlap"

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 顶部三大 LCD 状态指示仪
        hud_layout = QHBoxLayout()
        self.hud_coverage = self.create_glow_hud("路堤轨迹覆盖率", "0.0 %", "合格临界标准: 98%")
        self.hud_qualified = self.create_glow_hud("遍数达标率 (>=4P)", "0.0 %", "代表路基底基层密实质量")
        self.hud_deviate = self.create_glow_hud("过振剪切高风险区", "0.0 %", "防止颗粒级配破碎离析")
        
        hud_layout.addWidget(self.hud_coverage)
        hud_layout.addWidget(self.hud_qualified)
        hud_layout.addWidget(self.hud_deviate)
        layout.addLayout(hud_layout)

        # 主工作分幅区
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧物理机具设置边栏
        sidebar = QFrame()
        sidebar.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)

        lbl_menu = QLabel("🚜 摊铺后轨迹碾压仿真")
        lbl_menu.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-bottom: 8px;")
        sidebar_layout.addWidget(lbl_menu)

        # 车辆自动驾驶滚装轨迹模式
        lbl_mode = QLabel("自动碾压行进规迹预设:")
        lbl_mode.setStyleSheet("color: #94a3b8; font-size: 10px;")
        sidebar_layout.addWidget(lbl_mode)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["平行错轴叠轮 (Parallel)", "交叉网格错轴 (Cross-Hatch)", "Steering不均匀漂移"])
        self.cmb_mode.setStyleSheet("""
            QComboBox { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 6px; border-radius: 4px; font-size: 11px; }
            QComboBox QAbstractItemView { background-color: #0f172a; color: white; selection-background-color: #0ea5e9; }
        """)
        self.cmb_mode.currentIndexChanged.connect(self.on_mode_changed)
        sidebar_layout.addWidget(self.cmb_mode)
        sidebar_layout.addSpacing(5)

        # 钢轮宽度滑块
        self.lbl_drum = QLabel(f"压实轮额定钢轮宽: {self.drum_width} 米")
        self.lbl_drum.setStyleSheet("color: #94a3b8; font-size: 10px;")
        sidebar_layout.addWidget(self.lbl_drum)
        
        self.sld_drum = QSlider(Qt.Orientation.Horizontal)
        self.sld_drum.setRange(2, 12)
        self.sld_drum.setValue(self.drum_width)
        self.sld_drum.valueChanged.connect(self.on_drum_changed)
        sidebar_layout.addWidget(self.sld_drum)
        sidebar_layout.addSpacing(5)

        # 偏移行驶误差滑块
        self.lbl_drift = QLabel(f"机车行驶轮迹横飘误差: ±{self.steering_drift} 米")
        self.lbl_drift.setStyleSheet("color: #94a3b8; font-size: 10px;")
        sidebar_layout.addWidget(self.lbl_drift)
        
        self.sld_drift = QSlider(Qt.Orientation.Horizontal)
        self.sld_drift.setRange(0, 4)
        self.sld_drift.setValue(self.steering_drift)
        self.sld_drift.valueChanged.connect(self.on_drift_changed)
        sidebar_layout.addWidget(self.sld_drift)
        sidebar_layout.addSpacing(15)

        # 运动仿真按钮组
        self.btn_auto_drive = QPushButton("▶ 启动机具自适应巡航")
        self.btn_auto_drive.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; padding: 11px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #34d399; }
        """)
        self.btn_auto_drive.clicked.connect(self.toggle_auto_drive)
        sidebar_layout.addWidget(self.btn_auto_drive)

        btn_clear = QPushButton("🔄 重建待检铺筑段层")
        btn_clear.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; padding: 10px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background-color: #f87171; }
        """)
        btn_clear.clicked.connect(self.clear_grid)
        sidebar_layout.addWidget(btn_clear)

        sidebar_layout.addStretch()
        
        # 增加手动绘图说明小卡片
        manual_card = QFrame()
        manual_card.setStyleSheet("background-color: #0f172a; border-radius: 6px; border: 1px solid #334155; padding: 8px;")
        mc_layout = QVBoxLayout(manual_card)
        lbl_mc = QLabel("💡 触控交互提示\n支持鼠标直接在右侧图纸中“点击/划拉拖动”，即可手动驾驶钢轮，实时输出动态压实轨迹。")
        lbl_mc.setWordWrap(True)
        lbl_mc.setStyleSheet("color: #64748b; font-size: 9px; line-height: 12px;")
        mc_layout.addWidget(lbl_mc)
        sidebar_layout.addWidget(manual_card)

        main_splitter.addWidget(sidebar)

        # 右侧：上方为二维网格大图，下方为频数统计直方图
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.grid_canvas = NeonPassCountGrid()
        self.grid_canvas.inspect_cell_hovered.connect(self.on_matrix_hovered)
        right_layout.addWidget(self.grid_canvas, stretch=3)

        self.histogram_canvas = NeonPassCountHistogram()
        right_layout.addWidget(self.histogram_canvas, stretch=1)

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([260, 780])
        layout.addWidget(main_splitter)

        # 底部诊断与指令终端
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setPlaceholderText(">> 待检段落[K102+000 ~ K102+100]压实轨迹监控控制台...")
        self.terminal_log.setStyleSheet("""
            QTextEdit { background-color: #0b0f19; color: #10b981; border: 1px solid #334155; 
                        border-radius: 6px; padding: 10px; font-family: 'Consolas'; font-size: 11px; }
        """)
        self.terminal_log.setFixedHeight(120)
        bottom_layout.addWidget(self.terminal_log, stretch=3)

        # 变异性诊断卡
        self.diagnostic_table = QTableWidget(4, 2)
        self.diagnostic_table.setHorizontalHeaderLabels(["动态质检项目", "判定诊断"])
        self.diagnostic_table.setStyleSheet("""
            QTableWidget { background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155; gridline-color: #334155; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; }
        """)
        self.diagnostic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.diagnostic_table.setFixedWidth(300)
        self.diagnostic_table.setFixedHeight(120)
        self.diagnostic_table.setItem(0, 0, QTableWidgetItem("漏压缺压危险"))
        self.diagnostic_table.setItem(1, 0, QTableWidgetItem("过振剪切危险"))
        self.diagnostic_table.setItem(2, 0, QTableWidgetItem("路面压实度均匀度"))
        self.diagnostic_table.setItem(3, 0, QTableWidgetItem("推荐终压指令"))
        bottom_layout.addWidget(self.diagnostic_table, stretch=1)

        layout.addLayout(bottom_layout)

        # 进度指示
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #0f172a; color: white; text-align: center; border: 1px solid #334155; border-radius: 4px; height: 16px; font-size: 10px; }
            QProgressBar::chunk { background-color: #10b981; }
        """)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 初次统计算法触发
        self.recalculate_metrics()

    def create_glow_hud(self, title, val, sub):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        lbl_val = QLabel(val)
        lbl_val.setStyleSheet("color: #0ea5e9; font-size: 24px; font-weight: bold; font-family: 'Consolas';")
        
        lbl_sub = QLabel(sub)
        lbl_sub.setStyleSheet("color: #64748b; font-size: 9px;")

        layout.addWidget(lbl_t)
        layout.addWidget(lbl_val)
        layout.addWidget(lbl_sub)

        frame.lbl_val = lbl_val
        return frame

    def on_mode_changed(self, idx):
        modes = ["Parallel Overlap", "Cross Hatching", "Steering Drift"]
        self.auto_rolling_mode = modes[idx]
        self.write_log(f"[指令变更] 轨迹行驶模式重调为: {self.auto_rolling_mode}")

    def on_drum_changed(self, val):
        self.drum_width = val
        self.lbl_drum.setText(f"压实轮额定钢轮宽: {self.drum_width} 米")

    def on_drift_changed(self, val):
        self.steering_drift = val
        self.lbl_drift.setText(f"机车行驶轮迹横飘误差: ±{self.steering_drift} 米")

    def toggle_auto_drive(self):
        if not self.auto_timer.isActive():
            self.auto_timer.start(50) # 快速仿真频率
            self.btn_auto_drive.setText("⏸ 挂起机具自动驾驶")
            self.btn_auto_drive.setStyleSheet("background-color: #ef4444; color: white; padding: 11px; border-radius: 4px; font-weight: bold;")
            self.write_log(">> [车载巡航开始] 钢轮压路机自动驾驶行驶轨迹已连接，开始扫描...")
        else:
            self.auto_timer.stop()
            self.btn_auto_drive.setText("▶ 启动机具自适应巡航")
            self.btn_auto_drive.setStyleSheet("background-color: #10b981; color: white; padding: 11px; border-radius: 4px; font-weight: bold;")
            self.write_log(">> [巡航暂停] 机具自动行驶中断。当前数据已被保留。")

    def clear_grid(self):
        self.grid_canvas.matrix = np.zeros((self.grid_canvas.rows, self.grid_canvas.cols), dtype=int)
        self.grid_canvas.update()
        self.recalculate_metrics()
        self.write_log(">> [重建底基层] 清空当前铺筑路槽所有点位的历史轨迹，路面已恢复至零压实底。")

    def write_log(self, text):
        self.terminal_log.append(text)

    # ================= 4. 自动行驶仿真核心动力学算法 =================
    def advance_simulated_vehicle(self):
        """核心仿真逻辑：根据行驶轨迹动力学模型，模拟压路机轮子逐格碾压物理路面"""
        cols = self.grid_canvas.cols
        rows = self.grid_canvas.rows

        # X轴位移步进
        self.vehicle_x += self.vehicle_direction
        
        # 边界折返及车道变换
        if self.vehicle_x >= cols or self.vehicle_x < 0:
            self.vehicle_direction *= -1
            self.vehicle_x += self.vehicle_direction
            
            # 折返时变换车道
            if self.auto_rolling_mode == "Parallel Overlap":
                # 平行错轴：依次换到下一条车道
                self.sim_lane = (self.sim_lane + 6) % (rows - 4)
                if self.sim_lane < 3:
                    self.sim_lane = 3
            elif self.auto_rolling_mode == "Cross Hatching":
                # 交叉网格：横向移动距离变大
                self.sim_lane = (self.sim_lane + 11) % (rows - 4)
                if self.sim_lane < 3:
                    self.sim_lane = 3
            else:
                # 随机漂移行驶
                self.sim_lane = random.randint(3, rows - 4)

        # 考虑飘移物理误差
        drift_offset = 0
        if self.steering_drift > 0:
            drift_offset = random.randint(-self.steering_drift, self.steering_drift)

        target_row_center = self.sim_lane + drift_offset
        half_w = self.drum_width // 2

        # 给车轮覆盖的网格点叠施加一遍压实能量
        for r in range(target_row_center - half_w, target_row_center + half_w + 1):
            if 0 <= r < rows and 0 <= self.vehicle_x < cols:
                self.grid_canvas.matrix[r, self.vehicle_x] = min(self.grid_canvas.matrix[r, self.vehicle_x] + 1, 10)

        # 触发物理重绘
        self.grid_canvas.update()
        self.recalculate_metrics()

    # ================= 5. 多维质量数据统计算法 =================
    def recalculate_metrics(self):
        matrix = self.grid_canvas.matrix
        total_cells = matrix.size
        
        # 覆盖率 (遍数 >= 1 的占比)
        worked_cells = np.count_nonzero(matrix >= 1)
        coverage_pct = (worked_cells / total_cells) * 100.0
        
        # 达标率 (合格复压，遍数 >= 4P 的比例)
        target_cells = np.count_nonzero(matrix >= 4)
        qualified_pct = (target_cells / total_cells) * 100.0
        
        # 过压破坏率 (振幅破坏，遍数 >= 7P 比例)
        over_compacted_cells = np.count_nonzero(matrix >= 7)
        over_pct = (over_compacted_cells / total_cells) * 100.0

        # 更新大屏
        self.hud_coverage.lbl_val.setText(f"{coverage_pct:.1f} %")
        self.hud_qualified.lbl_val.setText(f"{qualified_pct:.1f} %")
        self.hud_deviate.lbl_val.setText(f"{over_pct:.1f} %")

        # 柱状直方图刷新
        self.histogram_canvas.update_frequencies(matrix)

        # 变异性与合格度诊断系统
        uncompacted_area = 100.0 - coverage_pct
        leakage_warning = "高危 (有大面积漏压)" if uncompacted_area > 5.0 else ("轻微漏压" if uncompacted_area > 0.1 else "合格 (零漏压)")
        over_warning = "极高风险 (过振析离)" if over_pct > 8.0 else ("合格" if over_pct == 0.0 else "局部剪切破坏预警")
        
        std_passes = np.std(matrix)
        uniformity = "极佳 (高度均匀)" if std_passes < 1.2 else ("合格" if std_passes <= 2.2 else "极差 (厚度不均/起步不稳)")

        recommend_action = "停止作业" if over_pct > 8.0 else ("全路幅全面压实" if coverage_pct < 98.0 else "初压完成，准予终压")

        self.diagnostic_table.setItem(0, 1, QTableWidgetItem(leakage_warning))
        self.diagnostic_table.setItem(1, 1, QTableWidgetItem(over_warning))
        self.diagnostic_table.setItem(2, 1, QTableWidgetItem(uniformity))
        self.diagnostic_table.setItem(3, 1, QTableWidgetItem(recommend_action))
        
        for i in range(4):
            self.diagnostic_table.item(i, 1).setForeground(QBrush(QColor("#38bdf8")))

        # 进度条
        self.progress_bar.setValue(int(qualified_pct))

    def on_matrix_hovered(self, col, row, val):
        """鼠标探针回传，直接写入诊断终端，模拟实时的遥测诊断"""
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'status_bar'):
                # 联动父窗口的状态栏
                parent.status_bar.showMessage(f"激光遥感探针锁定桩号: K102+{col}m | 横向宽度: {row}m | 碾压数据: {val}P")
                break
            parent = parent.parent()