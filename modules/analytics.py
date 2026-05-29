# modules/analytics.py
import math
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QSlider, 
                             QMessageBox, QLabel, QFrame, QSplitter, QTextEdit, QComboBox)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient

# ================= 1. 自研高动态高斯概率密度 Bell 曲线画布 =================
class NeonProbabilityDistributionCanvas(QWidget):
    # 自研的原生高斯正态概率密度曲线（Bell Curve）画布。
    # 动态绘制高斯概率包络带、中轴期望线、合格限制警戒线。
    # 支持鼠标随动激光探针进行概率积分查询。
    hover_coords_changed = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(350)
        self.setMouseTracking(True)
        
        # 数理统计控制参数
        self.mean_val = 80.0   # 均值 mu
        self.std_dev = 8.0     # 标准差 sigma
        self.target_limit = 75.0 # 设计要求刚度限
        
        # 悬浮指示参数
        self.hover_active = False
        self.hover_x_val = 0.0

    def load_statistics(self, mu, sigma, target):
        self.mean_val = mu
        self.std_dev = sigma
        self.target_limit = target
        self.hover_active = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#090d16")) # 酷黑太空底色

        # 留出刻度轴边界
        margin_l, margin_r = 55, 35
        margin_t, margin_b = 40, 45
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b

        # 刚度轴 CMV 量程: 30 - 130 CMV
        min_x, max_x = 30.0, 130.0
        # 概率轴上限归一化: 0% - 10%
        min_y, max_y = 0.0, 0.10

        def to_pixel(x, y):
            px = margin_l + ((x - min_x) / (max_x - min_x)) * plot_w
            py = margin_t + (1.0 - (y - min_y) / (max_y - min_y)) * plot_h
            return px, py

        # 1. 绘制网格线与科学刻度
        pen_grid = QPen(QColor("#1e293b"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_grid)
        
        # 横轴 CMV (每 10 CMV 一道)
        for val in range(30, 131, 10):
            px, _ = to_pixel(val, min_y)
            painter.drawLine(int(px), margin_t, int(px), h - margin_b)
            
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(int(px) - 10, h - margin_b + 18, f"{val}")
            painter.setPen(pen_grid)

        # 纵轴 概率百分比 (每 2.5% 一道)
        for i in range(5):
            val = i * 0.025
            _, py = to_pixel(min_x, val)
            painter.drawLine(margin_l, int(py), w - margin_r, int(py))
            
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(margin_l - 38, int(py) + 4, f"{val*100.0:.1f}%")
            painter.setPen(pen_grid)

        # 2. 绘制置信区间概率填充 (1σ - 3σ 绿光渐变发光区域)
        # 这里用置信带展示，符合大数定律概率分布
        grad = QLinearGradient(0, margin_t, 0, h - margin_b)
        grad.setColorAt(0.0, QColor(16, 185, 129, 30)) # 翡翠绿
        grad.setColorAt(1.0, QColor(16, 185, 129, 5))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)

        # 1σ 边界映射
        s_1_x, _ = to_pixel(self.mean_val - self.std_dev, 0)
        e_1_x, _ = to_pixel(self.mean_val + self.std_dev, 0)
        painter.drawRect(QRectF(s_1_x, margin_t, e_1_x - s_1_x, plot_h))

        # 3. 连续采样计算并绘制高斯正态概率 Bell 曲线
        samples_x = np.linspace(min_x, max_x, 150)
        # 高斯函数: y = (1 / (sigma * sqrt(2*pi))) * exp(-0.5 * ((x - mu)/sigma)^2)
        samples_y = []
        for x_val in samples_x:
            exponent = -0.5 * ((x_val - self.mean_val) / self.std_dev) ** 2
            pdf_val = (1.0 / (self.std_dev * math.sqrt(2 * math.pi))) * math.exp(exponent)
            samples_y.append(pdf_val)

        pts = []
        for i in range(len(samples_x)):
            px, py = to_pixel(samples_x[i], samples_y[i])
            pts.append(QPointF(px, py))

        # 绘制主正态曲线 (高亮青色霓虹)
        painter.setPen(QPen(QColor("#0ea5e9"), 2, Qt.PenStyle.SolidLine))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i+1])

        # 4. 绘制数学期望线 (μ 中轴线 - 黄色)
        mu_px, _ = to_pixel(self.mean_val, min_y)
        painter.setPen(QPen(QColor("#eab308"), 1.2, Qt.PenStyle.DashDotLine))
        painter.drawLine(int(mu_px), margin_t, int(mu_px), h - margin_b)
        
        painter.setPen(QColor("#eab308"))
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(int(mu_px) + 6, margin_t + 18, f"Mean μ: {self.mean_val:.1f}")

        # 5. 绘制设计最低合格刚度红线 (JTG 限制限)
        lim_px, _ = to_pixel(self.target_limit, min_y)
        painter.setPen(QPen(QColor("#f43f5e"), 1.2, Qt.PenStyle.SolidLine))
        painter.drawLine(int(lim_px), margin_t, int(lim_px), h - margin_b)
        
        painter.setPen(QColor("#f43f5e"))
        painter.drawText(int(lim_px) - 85, margin_t + 18, f"Limit: {self.target_limit:.1f}")

        # 6. 鼠标探针随动激光线与浮动 HUD
        if self.hover_active and min_x <= self.hover_x_val <= max_x:
            exponent = -0.5 * ((self.hover_x_val - self.mean_val) / self.std_dev) ** 2
            pdf_val = (1.0 / (self.std_dev * math.sqrt(2 * math.pi))) * math.exp(exponent)
            
            hx, hy = to_pixel(self.hover_x_val, pdf_val)

            # 激光束竖线
            painter.setPen(QPen(QColor("#38bdf8"), 1, Qt.PenStyle.SolidLine))
            painter.drawLine(int(hx), margin_t, int(hx), h - margin_b)

            # 发光十字标靶
            painter.setBrush(QBrush(QColor("#38bdf8")))
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawEllipse(QPointF(hx, hy), 5, 5)

            # 弹出 HUD 数据卡
            box_w, box_h = 160, 65
            bx = hx + 12 if hx + box_w + 12 < w else hx - box_w - 12
            by = hy - 35 if hy - 35 > margin_t else margin_t

            painter.fillRect(QRectF(bx, by, box_w, box_h), QBrush(QColor(15, 23, 42, 220)))
            painter.setPen(QPen(QColor("#38bdf8"), 1))
            painter.drawRect(QRectF(bx, by, box_w, box_h))

            # 绘制 HUD 内文本
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(bx + 10), int(by + 18), f"STIFFNESS : {self.hover_x_val:.1f}")
            painter.drawText(int(bx + 10), int(by + 34), f"PROB DENS : {pdf_val*100.0:.2f}%")
            
            # Z-score 指标
            z_val = (self.hover_x_val - self.mean_val) / self.std_dev
            painter.setPen(QColor("#a855f7"))
            painter.drawText(int(bx + 10), int(by + 50), f"Z-SCORE   : {z_val:.2f}σ")

        # 水印和注释
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(15, margin_t - 15, "高斯测绘: 大数定律概率离散度仿真图谱")

    def mouseMoveEvent(self, event):
        margin_l = 55
        margin_r = 35
        plot_w = self.width() - margin_l - margin_r
        
        mx = event.position().x()
        if mx < margin_l or mx > self.width() - margin_r:
            self.hover_active = False
            self.update()
            return

        # 反向求解 CMV 的值
        rel_x = (mx - margin_l) / plot_w
        self.hover_x_val = 30.0 + rel_x * 100.0 # 30 - 130 范围
        self.hover_active = True
        
        # 实时概率输出
        exponent = -0.5 * ((self.hover_x_val - self.mean_val) / self.std_dev) ** 2
        pdf_val = (1.0 / (self.std_dev * math.sqrt(2 * math.pi))) * math.exp(exponent)
        
        self.hover_coords_changed.emit(self.hover_x_val, pdf_val)
        self.update()

    def leaveEvent(self, event):
        self.hover_active = False
        self.update()

# ================= 2. 统计分析主控制面板 =================
class AnalyticsWidget(QWidget):
    # 统计分析与概率分布主界面。
    # 结合高斯密度算法、Descriptive Statistics 描述性统计算法。
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始数理参数
        self.target_mean = 82.5   # 均值
        self.target_std = 7.5     # 标准差 (大变异/小变异)
        self.acceptance_limit = 75.0
        self.sample_size = 500    # 大样本容量

        self.init_ui()
        self.run_descriptive_analysis()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. 顶部数理统计指标 HUD 板
        stats_panel = QHBoxLayout()
        self.hud_samples = self.create_glow_hud("数理统计有效样本 (N)", "500", "累计归档大样本容量")
        self.hud_homogeneity = self.create_glow_hud("路基刚度均匀度评价", "良 (GOOD)", "代表路面压实稳定性")
        self.hud_outliers = self.create_glow_hud("检出缺陷风险异常点", "0 点", "通过 Hampel 离群法剥离")
        stats_panel.addWidget(self.hud_samples)
        stats_panel.addWidget(self.hud_homogeneity)
        stats_panel.addWidget(self.hud_outliers)
        layout.addLayout(stats_panel)

        # 2. 中部核心区：左侧控制栏 + 中间描述性统计表 + 右侧高斯概率图
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧数理调节侧边栏
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)

        lbl_sec1 = QLabel("⚙ 概率参数及期望值控制")
        lbl_sec1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_sec1)

        # 大样本容量设置
        lbl_sz = QLabel("大样本采样估算规模:")
        lbl_sz.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(lbl_sz)
        
        self.cmb_samples = QComboBox()
        self.cmb_samples.addItems(["N = 200 连续采样点", "N = 500 连续采样点", "N = 1000 连续采样点"])
        self.cmb_samples.currentIndexChanged.connect(self.on_sample_size_changed)
        ctrl_layout.addWidget(self.cmb_samples)
        ctrl_layout.addSpacing(5)

        # 均值 μ 滑块 (代表期望质量)
        self.lbl_mean = QLabel(f"刚度数学期望均值 (μ): {self.target_mean:.1f} CMV")
        self.lbl_mean.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(self.lbl_mean)
        
        self.sld_mean = QSlider(Qt.Orientation.Horizontal)
        self.sld_mean.setRange(50, 110) # 50.0 - 110.0 CMV
        self.sld_mean.setValue(int(self.target_mean))
        self.sld_mean.valueChanged.connect(self.on_mean_changed)
        ctrl_layout.addWidget(self.sld_mean)
        ctrl_layout.addSpacing(5)

        # 标准差 σ 滑块 (代表变异度)
        self.lbl_std = QLabel(f"地质刚度离散标准差 (σ): {self.target_std:.1f}")
        self.lbl_std.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ctrl_layout.addWidget(self.lbl_std)
        
        self.sld_std = QSlider(Qt.Orientation.Horizontal)
        self.sld_std.setRange(3, 18) # 3.0 - 18.0
        self.sld_std.setValue(int(self.target_std))
        self.sld_std.valueChanged.connect(self.on_std_changed)
        ctrl_layout.addWidget(self.sld_std)
        ctrl_layout.addSpacing(15)

        # 触发运行按钮
        self.btn_run = QPushButton("⚡ 执行概率分布解算")
        self.btn_run.setStyleSheet("""
            QPushButton { background-color: #0284c7; color: white; padding: 10px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #0ea5e9; }
        """)
        self.btn_run.clicked.connect(self.run_descriptive_analysis)
        ctrl_layout.addWidget(self.btn_run)

        # 控件统一样式
        self.setStyleSheet("""
            QComboBox { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 6px; border-radius: 4px; font-size: 11px; }
            QComboBox QAbstractItemView { background-color: #0f172a; color: white; selection-background-color: #0ea5e9; }
        """)

        ctrl_layout.addStretch()
        main_splitter.addWidget(ctrl_frame)

        # 中部：描述性统计指标大列表
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget(6, 2)
        self.table.setHorizontalHeaderLabels(["描述统计项目 (Descriptive)", "大样本概率值"])
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0f172a; color: #f1f5f9; border: 1px solid #334155; gridline-color: #1e293b; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; font-weight: bold; }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setItem(0, 0, QTableWidgetItem("算术期望均值 Mean"))
        self.table.setItem(1, 0, QTableWidgetItem("极差极值 Span"))
        self.table.setItem(2, 0, QTableWidgetItem("中位数 Median"))
        self.table.setItem(3, 0, QTableWidgetItem("大样本变异系数 CoV"))
        self.table.setItem(4, 0, QTableWidgetItem("正态分布 Skewness (偏度)"))
        self.table.setItem(5, 0, QTableWidgetItem("JTG F80 单侧合格限界"))
        table_layout.addWidget(self.table)

        main_splitter.addWidget(table_frame)

        # 右侧：正态分布图
        curve_frame = QFrame()
        curve_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        curve_layout = QVBoxLayout(curve_frame)
        curve_layout.setContentsMargins(10, 10, 10, 10)

        self.curve_canvas = NeonProbabilityDistributionCanvas()
        self.curve_canvas.hover_coords_changed.connect(self.on_canvas_probe_moved)
        curve_layout.addWidget(self.curve_canvas)

        main_splitter.addWidget(curve_frame)

        # 调整三幅占比 2.2 : 4.8 : 3
        main_splitter.setSizes([220, 480, 300])
        layout.addWidget(main_splitter)

        # 底部大数诊断日志终端
        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setPlaceholderText(">> 统计大数分析控制总线就绪...")
        self.terminal_log.setStyleSheet("""
            QTextEdit { background-color: #0b0f19; color: #38bdf8; border: 1px solid #334155; 
                        border-radius: 6px; padding: 10px; font-family: 'Consolas', monospace; font-size: 11px; }
        """)
        self.terminal_log.setFixedHeight(100)
        layout.addWidget(self.terminal_log)

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

    def write_log(self, text):
        self.terminal_log.append(f"[{datetime_now_str()}] {text}")

    def on_sample_size_changed(self, idx):
        sizes = [200, 500, 1000]
        self.sample_size = sizes[idx]
        self.hud_samples.lbl_val.setText(str(self.sample_size))
        self.run_descriptive_analysis()

    def on_mean_changed(self, val):
        self.target_mean = float(val)
        self.lbl_mean.setText(f"刚度数学期望均值 (μ): {self.target_mean:.1f} CMV")
        self.run_descriptive_analysis()

    def on_std_changed(self, val):
        self.target_std = float(val)
        self.lbl_std.setText(f"地质刚度离散标准差 (σ): {self.target_std:.1f}")
        self.run_descriptive_analysis()

    # ================= 3. 核心描述性统计学解算系统 =================
    def run_descriptive_analysis(self):
        # 1. 采用蒙特卡洛数理统计发生器，生成满足特定期望和标准差的大样本刚度测点
        np.random.seed(88)
        raw_samples = np.random.normal(self.target_mean, self.target_std, self.sample_size)
        
        # 模拟路基大孤石带来的正右偏离群点 (极值异常点)
        raw_samples[int(self.sample_size * 0.12)] = 125.4
        raw_samples[int(self.sample_size * 0.85)] = 129.1

        # 2. 描述性统计解算
        mean_val = float(np.mean(raw_samples))
        median_val = float(np.median(raw_samples))
        min_val = float(np.min(raw_samples))
        max_val = float(np.max(raw_samples))
        std_val = float(np.std(raw_samples))
        
        cov = std_val / mean_val if mean_val > 0 else 0.0 # 变异系数

        # 解算正偏度 (Skewness)
        diff_cubed = (raw_samples - mean_val) ** 3
        skewness = float(np.mean(diff_cubed) / (std_val ** 3))

        # Hampel 统计离群点检测 (剥离由于打在孤石上产生的突变点)
        local_median = np.median(raw_samples)
        local_mad = np.median(np.abs(raw_samples - local_median))
        outlier_threshold = 2.5 * local_mad
        outliers_count = int(np.sum(np.abs(raw_samples - local_median) > outlier_threshold))

        # 3. 均匀度评级与 HUD 数据刷写
        if cov <= 0.08:
            homo_rating = "极佳 (EXCELLENT)"
            self.hud_homogeneity.lbl_val.setStyleSheet("color: #10b981; font-size: 24px; font-weight: bold; font-family: 'Consolas';")
        elif cov <= 0.13:
            homo_rating = "良好 (GOOD)"
            self.hud_homogeneity.lbl_val.setStyleSheet("color: #0ea5e9; font-size: 24px; font-weight: bold; font-family: 'Consolas';")
        else:
            homo_rating = "较差 (VARIED)"
            self.hud_homogeneity.lbl_val.setStyleSheet("color: #f43f5e; font-size: 24px; font-weight: bold; font-family: 'Consolas';")

        self.hud_homogeneity.lbl_val.setText(homo_rating)
        self.hud_outliers.lbl_val.setText(f"{outliers_count} 点次")

        # 4. 刷新右侧高斯概率密度 Bell 画布
        self.curve_canvas.load_statistics(self.target_mean, self.target_std, self.acceptance_limit)

        # 5. 填装 Descriptive 统计表
        self.table.setItem(0, 1, QTableWidgetItem(f"{mean_val:.2f} CMV"))
        self.table.setItem(1, 1, QTableWidgetItem(f"{min_val:.1f} ~ {max_val:.1f} CMV (R={max_val-min_val:.1f})"))
        self.table.setItem(2, 1, QTableWidgetItem(f"{median_val:.2f} CMV"))
        self.table.setItem(3, 1, QTableWidgetItem(f"{cov:.4f} (均质度良好)" if cov <= 0.12 else f"{cov:.4f} (离散过高)"))
        self.table.setItem(4, 1, QTableWidgetItem(f"{skewness:.3f} (中度右偏)" if skewness > 0.5 else f"{skewness:.3f} (近似对称)"))
        
        # JTG F80 单侧置信评定下限 (k=0.75系数)
        rep_val = mean_val - 0.75 * std_val
        rep_status = "合格" if rep_val >= self.acceptance_limit else "不合格"
        self.table.setItem(5, 1, QTableWidgetItem(f"{rep_val:.2f} CMV [{rep_status}]"))

        # 为表格上色
        for i in range(6):
            self.table.item(i, 1).setForeground(QBrush(QColor("#38bdf8")))

        # 写日志终端
        self.write_log(f"--- [descriptive descriptive 大数质检评定审计] ---")
        self.write_log(f">> 统计样本: N={self.sample_size} | 数学期望设定 μ: {self.target_mean} | 物理标准偏差 σ: {self.target_std}")
        self.write_log(f">> 算术均值: {mean_val:.3f} CMV | 离散标准差: {std_val:.3f} | 变异系数 CoV: {cov:.4f}")
        self.write_log(f">> 大数概率模型解算：由于地基大石块阻碍产生的右偏度 Skewness: {skewness:.4f}")
        self.write_log(f">> 代表性压实下限 (LCL): {rep_val:.3f} CMV | 一致性综合评价: {homo_rating}")

    def on_canvas_probe_moved(self, cmv, density):
        # 雷达随动探针联动到主 MainWindow 的状态栏
        msg = f"大数概率密度传感器探针反馈: 模拟刚度: {cmv:.1f} CMV | 拟合概率密度: {density*100.0:.3f}%"
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'status_bar'):
                parent.status_bar.showMessage(msg)
                break
            parent = parent.parent()

def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime('%H:%M:%S')