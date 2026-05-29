# modules/soil_standard.py
import sqlite3
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, 
                             QMessageBox, QLabel, QFrame, QSplitter, QComboBox, QTextEdit)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient
from core.database import get_connection

# ================= 1. 自研原生高科技击实曲线画布 =================
class NeonCompactionCurveCanvas(QWidget):
    # 自研的原生击实抛物线拟合画布。
    # 依据 Proctor 击实方程：y = max_density - beta * (x - opt_moisture)^2 动态绘制击实包络。
    # 支持鼠标随动激光探针。
    hover_coords_changed = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(350)
        self.setMouseTracking(True)
        
        # 物理控制变量
        self.soil_type = "未加载"
        self.max_density = 2.05 # g/cm3
        self.opt_moisture = 10.5 # %
        self.beta = 0.025 # 曲率
        
        # 交互指示变量
        self.hover_active = False
        self.hover_x_val = 0.0
        self.hover_y_val = 0.0

    def load_soil_parameters(self, soil_type, mdd, omc):
        self.soil_type = soil_type
        self.max_density = mdd
        self.opt_moisture = omc
        
        # 根据土分类自动设定曲率，砾石突变陡峭，粘土平缓
        if "砂" in soil_type or "砾" in soil_type:
            self.beta = 0.045
        elif "粘" in soil_type or "泥" in soil_type:
            self.beta = 0.012
        else:
            self.beta = 0.025
            
        self.hover_active = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#090d16")) # 深黑色背景

        # 留出刻度轴边界
        margin_l, margin_r = 50, 30
        margin_t, margin_b = 40, 45
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b

        # 物理量程限制：含水率 0% - 25%, 干密度 1.0 - 2.5 g/cm³
        min_x, max_x = 0.0, 25.0
        min_y, max_y = 1.0, 2.5

        def to_pixel(x, y):
            px = margin_l + ((x - min_x) / (max_x - min_x)) * plot_w
            py = margin_t + (1.0 - (y - min_y) / (max_y - min_y)) * plot_h
            return px, py

        # 1. 绘制网格刻度线
        pen_grid = QPen(QColor("#1e293b"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_grid)
        
        # 含水率横向轴 (每 5% 一道)
        for val in range(0, 26, 5):
            px, _ = to_pixel(val, min_y)
            painter.drawLine(int(px), margin_t, int(px), h - margin_b)
            
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(int(px) - 10, h - margin_b + 18, f"{val}%")
            painter.setPen(pen_grid)

        # 密度纵向轴
        for i in range(4):
            val = 1.0 + i * 0.5
            _, py = to_pixel(min_x, val)
            painter.drawLine(margin_l, int(py), w - margin_r, int(py))
            
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(margin_l - 32, int(py) + 4, f"{val:.1f}")
            painter.setPen(pen_grid)

        # 2. 连续采样计算并绘制 Proctor 击实抛物线
        samples_x = np.linspace(min_x, max_x, 150)
        # y = max_density - beta * (x - opt_moisture)^2
        samples_y = self.max_density - self.beta * (samples_x - self.opt_moisture) ** 2
        # 裁剪干密度下限不低于 1.0
        samples_y = np.clip(samples_y, 1.0, 2.5)

        pts = []
        for i in range(len(samples_x)):
            px, py = to_pixel(samples_x[i], samples_y[i])
            pts.append(QPointF(px, py))

        # 绘制主曲线 (霓虹青粗线)
        painter.setPen(QPen(QColor("#0ea5e9"), 2, Qt.PenStyle.SolidLine))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i+1])

        # 3. 绘制最佳击实交叉定位线 (OMC & MDD 点)
        opt_px, opt_py = to_pixel(self.opt_moisture, self.max_density)
        painter.setPen(QPen(QColor("#10b981"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(margin_l, int(opt_py), w - margin_r, int(opt_py))
        painter.drawLine(int(opt_px), margin_t, int(opt_px), h - margin_b)

        # 焦点处绘制绿色标靶同心圆
        painter.setBrush(QBrush(QColor(16, 185, 129, 80)))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawEllipse(QPointF(opt_px, opt_py), 8, 8)
        painter.drawEllipse(QPointF(opt_px, opt_py), 3, 3)

        # 4. 绘制悬浮激光探针
        if self.hover_active and min_x <= self.hover_x_val <= max_x:
            # 实时解算当前探针下的拟合密度值
            curr_density = self.max_density - self.beta * (self.hover_x_val - self.opt_moisture) ** 2
            curr_density = max(1.0, curr_density)
            
            hx, hy = to_pixel(self.hover_x_val, curr_density)

            # 绘制指示线
            painter.setPen(QPen(QColor("#f43f5e"), 1, Qt.PenStyle.SolidLine))
            painter.drawLine(int(hx), margin_t, int(hx), h - margin_b)

            # 发光十字点
            painter.setBrush(QBrush(QColor("#f43f5e")))
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawEllipse(QPointF(hx, hy), 5, 5)

            # 渲染迷你悬浮 HUD 窗
            box_w, box_h = 170, 70
            bx = hx + 12 if hx + box_w + 12 < w else hx - box_w - 12
            by = hy - 35 if hy - 35 > margin_t else margin_t

            painter.fillRect(QRectF(bx, by, box_w, box_h), QBrush(QColor(15, 23, 42, 220)))
            painter.setPen(QPen(QColor("#f43f5e"), 1))
            painter.drawRect(QRectF(bx, by, box_w, box_h))

            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(bx + 10), int(by + 18), f"MOISTURE : {self.hover_x_val:.1f} %")
            painter.drawText(int(bx + 10), int(by + 34), f"DRY DENS : {curr_density:.3f} g")
            
            deviation = self.hover_x_val - self.opt_moisture
            status_t = "DRY-SIDE" if deviation < -1.0 else ("WET-SIDE" if deviation > 1.0 else "OPTIMAL")
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(int(bx + 10), int(by + 52), f"ZONE     : {status_t}")

        # 图谱物理常数水印
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(15, margin_t - 15, f"当前拟合物理曲线: '{self.soil_type}' 击实抛物线模型")

    def mouseMoveEvent(self, event):
        margin_l = 50
        margin_r = 30
        plot_w = self.width() - margin_l - margin_r
        
        mx = event.position().x()
        if mx < margin_l or mx > self.width() - margin_r:
            self.hover_active = False
            self.update()
            return

        # 反向计算物理含水率值
        rel_x = (mx - margin_l) / plot_w
        self.hover_x_val = rel_x * 25.0
        self.hover_active = True
        
        # 实时解算反馈
        curr_density = self.max_density - self.beta * (self.hover_x_val - self.opt_moisture) ** 2
        self.hover_coords_changed.emit(self.hover_x_val, max(1.0, curr_density))
        self.update()

    def leaveEvent(self, event):
        self.hover_active = False
        self.update()

# ================= 2. 标准击实管理面板 =================
class SoilStandardWidget(QWidget):
    # 土质参数与击实标准管理。
    # 结合数据库读写，提供击实参数 CRUD 和回弹力学模量实时的敏感估算法。
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh_table()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. 顶部 HUD 显示屏组
        stats_panel = QHBoxLayout()
        self.hud_types = self.create_glow_hud("已登记物理土分类数", "0", "SQLite 规范库类型")
        self.hud_max_density = self.create_glow_hud("干密度基准上限 (MDD)", "2.20", "对应砂砾/骨料极限击实")
        self.hud_ideal_moisture = self.create_glow_hud("最佳含水量参考中值", "10.0 %", "黏土与粉粒土壤综合质控线")
        stats_panel.addWidget(self.hud_types)
        stats_panel.addWidget(self.hud_max_density)
        stats_panel.addWidget(self.hud_ideal_moisture)
        layout.addLayout(stats_panel)

        # 2. 中部核心区 (左侧录入与估算 + 中间列表表格 + 右侧击实图谱)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左边输入与物理公式模拟侧边栏
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)

        lbl_sec1 = QLabel("⚙ 登记填料物理击实标准")
        lbl_sec1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_sec1)

        # 字段录入
        self.cmb_class = QComboBox()
        self.cmb_class.addItems(["低液限粘土 (Clay)", "砂质粉土 (Silt)", "中粗砂 (Sand)", "级配碎石/砾石 (Gravel)"])
        ctrl_layout.addWidget(self.cmb_class)

        self.txt_density = QLineEdit()
        self.txt_density.setPlaceholderText("最大干密度 MDD (g/cm³)")
        ctrl_layout.addWidget(self.txt_density)

        self.txt_moisture = QLineEdit()
        self.txt_moisture.setPlaceholderText("最佳含水率 OMC (%)")
        ctrl_layout.addWidget(self.txt_moisture)

        # 表单功能按钮
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("💾 登记物理标准")
        self.btn_add.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; padding: 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #34d399; }
        """)
        self.btn_add.clicked.connect(self.add_soil)
        
        self.btn_del = QPushButton("🗑 物理注销")
        self.btn_del.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; padding: 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #f87171; }
        """)
        self.btn_del.clicked.connect(self.delete_soil)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        ctrl_layout.addLayout(btn_layout)

        ctrl_layout.addSpacing(15)

        # 土基回弹模量仿真器 (力学模拟器)
        lbl_sec2 = QLabel("🧠 土基回弹模量力学模拟器")
        lbl_sec2.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")
        ctrl_layout.addWidget(lbl_sec2)
        
        lbl_calc_desc = QLabel("输入当前路槽临时状态，动态估算路基物理回弹性刚度指标:")
        lbl_calc_desc.setWordWrap(True)
        lbl_calc_desc.setStyleSheet("color: #64748b; font-size: 9px; line-height: 12px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_calc_desc)

        self.txt_sim_moisture = QLineEdit()
        self.txt_sim_moisture.setPlaceholderText("实时实测含水率 (%)")
        self.txt_sim_moisture.textChanged.connect(self.recalculate_dynamic_modulus)
        ctrl_layout.addWidget(self.txt_sim_moisture)

        self.txt_sim_density = QLineEdit()
        self.txt_sim_density.setPlaceholderText("实时干密度 (g/cm³)")
        self.txt_sim_density.textChanged.connect(self.recalculate_dynamic_modulus)
        ctrl_layout.addWidget(self.txt_sim_density)

        # 模拟器输出框
        self.lbl_modulus_result = QLabel("路基估算回弹模量: -- MPa")
        self.lbl_modulus_result.setStyleSheet("""
            color: #10b981; font-family: 'Consolas', monospace; font-size: 11.5px; font-weight: bold; 
            background-color: #0b0f19; border: 1px solid #1e293b; padding: 8px; border-radius: 4px; margin-top: 5px;
        """)
        ctrl_layout.addWidget(self.lbl_modulus_result)

        # 控件统一样式
        self.setStyleSheet("""
            QComboBox { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 6px; border-radius: 4px; font-size: 11px; }
            QComboBox QAbstractItemView { background-color: #0f172a; color: white; selection-background-color: #0ea5e9; }
            QLineEdit { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 6px; border-radius: 4px; font-family: 'Consolas'; font-size: 11px; }
        """)

        ctrl_layout.addStretch()
        main_splitter.addWidget(ctrl_frame)

        # 中部：SQLite 数据表格
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["土质标准物理分类", "最大干密度 (g/cm³)", "最佳含水量 (%)"])
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0f172a; color: #f1f5f9; border: 1px solid #334155; gridline-color: #1e293b; }
            QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; font-weight: bold; }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        table_layout.addWidget(self.table)

        main_splitter.addWidget(table_frame)

        # 右侧：击实图谱
        curve_frame = QFrame()
        curve_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        curve_layout = QVBoxLayout(curve_frame)
        curve_layout.setContentsMargins(10, 10, 10, 10)

        self.curve_canvas = NeonCompactionCurveCanvas()
        self.curve_canvas.hover_coords_changed.connect(self.on_canvas_probe_moved)
        curve_layout.addWidget(self.curve_canvas)

        main_splitter.addWidget(curve_frame)

        # 配置中幅宽度占比 2.2 : 4.8 : 3
        main_splitter.setSizes([220, 480, 300])
        layout.addWidget(main_splitter)

        # 底部系统日志终端
        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setPlaceholderText(">> 土质标准力学控制总线就绪...")
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

    # ================= 3. 土工力学数据库 CRUD 逻辑 =================
    def refresh_table(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT soil_type, max_dry_density, optimum_moisture FROM soil_standards")
            rows = cursor.fetchall()
            
            self.table.setRowCount(0)
            mdd_list = []
            omc_list = []
            
            for r_idx, row_data in enumerate(rows):
                self.table.insertRow(r_idx)
                for c_idx, val in enumerate(row_data):
                    self.table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
                mdd_list.append(row_data[1])
                omc_list.append(row_data[2])
                
            # 刷新 HUD 数据看板
            self.hud_types.lbl_val.setText(str(len(rows)))
            if mdd_list:
                self.hud_max_density.lbl_val.setText(f"{max(mdd_list):.2f}")
                self.hud_ideal_moisture.lbl_val.setText(f"{np.median(omc_list):.1f} %")
                
        except Exception as e:
            self.write_log(f"数据载入错误: {str(e)}")
        finally:
            conn.close()

    def add_soil(self):
        soil = self.cmb_class.currentText().strip()
        density = self.txt_density.text().strip()
        moisture = self.txt_moisture.text().strip()
        
        if not density or not moisture:
            QMessageBox.warning(self, "校验提示", "最大干密度与最佳含水量不允许为空。")
            return
            
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO soil_standards (soil_type, max_dry_density, optimum_moisture) VALUES (?, ?, ?)",
                           (soil, float(density), float(moisture)))
            conn.commit()
            conn.close()
            
            self.write_log(f"新标准入库: '{soil}' (MDD: {density}g/cm³, OMC: {moisture}%)")
            self.refresh_table()
            self.txt_density.clear()
            self.txt_moisture.clear()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "数据库冲突", "登记失败：此分类标准的物理标准已存在于数据库中。")
        except Exception as e:
            QMessageBox.critical(self, "系统报错", f"写入错误: {str(e)}")

    def delete_soil(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "操作提示", "请先在列表中选中需要物理报废的参数标准。")
            return
            
        soil_type = self.table.item(curr_row, 0).text()
        
        reply = QMessageBox.question(self, "物理注销确认", f"确定彻底在规范库中物理注销土质标准 '{soil_type}' 吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM soil_standards WHERE soil_type=?", (soil_type,))
                conn.commit()
                self.write_log(f"标准物理注销成功: {soil_type}")
                self.refresh_table()
                self.curve_canvas.soil_type = "未加载"
                self.curve_canvas.update()
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))
            finally:
                conn.close()

    # ================= 4. 高阶交互：列表联动击实抛物线重绘 =================
    def on_table_selection_changed(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            return
            
        soil_type = self.table.item(curr_row, 0).text()
        mdd = float(self.table.item(curr_row, 1).text())
        omc = float(self.table.item(curr_row, 2).text())
        
        # 联动物理图画重画
        self.curve_canvas.load_soil_parameters(soil_type, mdd, omc)
        self.write_log(f"图纸物理图谱重构: K-Proctor 方程重新匹配至 '{soil_type}'")

        # 辅助填充到回弹模量输入计算框，省去手动输入
        self.txt_sim_density.setText(f"{mdd:.3f}")
        self.txt_sim_moisture.setText(f"{omc:.1f}")

    # ================= 5. 岩土回弹模量力学敏感估算算法 =================
    def recalculate_dynamic_modulus(self):
        m_text = self.txt_sim_moisture.text().strip()
        d_text = self.txt_sim_density.text().strip()
        
        if not m_text or not d_text:
            self.lbl_modulus_result.setText("路基估算回弹模量: -- MPa")
            return
            
        try:
            moisture = float(m_text)
            density = float(d_text)
            
            if moisture <= 0 or density <= 0:
                return

            # 基于土工经验公式: E0 = 60 * (density ^ 2.4) * (moisture ^ -0.65)
            # 模拟随着含水率上升（土变软），回弹模量急剧衰减的过程
            est_modulus = 60.0 * (density ** 2.4) * (moisture ** -0.65)
            # 乘以级配系数
            est_modulus = max(15.0, min(180.0, est_modulus * 10.0))
            
            self.lbl_modulus_result.setText(f"路基估算回弹模量: {est_modulus:.1f} MPa")
        except ValueError:
            pass

    def on_canvas_probe_moved(self, moisture, density):
        # 雷达随动探针联动到主 MainWindow 的状态栏
        msg = f"物理击实传感器探针反馈: 模拟含水量: {moisture:.1f}% | 拟合最大干密度: {density:.3f} g/cm³"
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'status_bar'):
                parent.status_bar.showMessage(msg)
                break
            parent = parent.parent()

def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime('%H:%M:%S')