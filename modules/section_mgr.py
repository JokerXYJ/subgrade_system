# modules/section_mgr.py
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, 
                             QMessageBox, QLabel, QFrame, QSplitter, QTextEdit)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QLinearGradient
from core.database import get_connection

# ================= 1. 自研原生桩号线性进度图谱画布 =================
class NeonLinearSectionCanvas(QWidget):
    # 自研的原生路段线性里程进度示踪器。
    # 在主轴上以荧光蓝色长条和高亮坐标标记当前标段起止桩号和规划空间范围。
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(350)
        
        # 物理控制量
        self.section_name = "未加载"
        self.start_ch = 0.0 # 起桩
        self.end_ch = 0.0 # 止桩
        self.has_active_section = False
        
        # 里程轴绝对基准：K102+000 到 K102+1500m
        self.axis_min = 0.0
        self.axis_max = 1500.0

    def load_section_parameters(self, name, start, end):
        self.section_name = name
        self.start_ch = start
        self.end_ch = end
        self.has_active_section = True
        self.update()

    def clear_canvas(self):
        self.has_active_section = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#090d16")) # 深黑色太空背景

        # 留出四周间距
        margin_l, margin_r = 40, 40
        plot_w = w - margin_l - margin_r
        center_y = h // 2

        # 1. 绘制一条横跨全屏的主干公路轴线 (暗灰色)
        pen_road = QPen(QColor("#1e293b"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_road)
        painter.drawLine(margin_l, center_y, w - margin_r, center_y)

        # 2. 绘制轴线刻度与桩号文本 (5等分，覆盖 0 - 1500 米范围)
        pen_tick = QPen(QColor("#475569"), 1.5, Qt.PenStyle.SolidLine)
        for i in range(6):
            frac = i / 5.0
            mile_val = self.axis_min + frac * (self.axis_max - self.axis_min)
            px = margin_l + frac * plot_w
            
            # 画刻度线
            painter.setPen(pen_tick)
            painter.drawLine(int(px), center_y - 12, int(px), center_y + 12)
            
            # 桩号字符
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(px) - 25, center_y + 30, f"K102+{int(mile_val)}")

        # 3. 绘制当前激活标段的范围带 (高亮氖蓝渐变)
        if self.has_active_section and self.end_ch > self.start_ch:
            # 比例折算
            s_frac = (self.start_ch - self.axis_min) / (self.axis_max - self.axis_min)
            e_frac = (self.end_ch - self.axis_min) / (self.axis_max - self.axis_min)
            
            # 约束范围
            s_frac = max(0.0, min(1.0, s_frac))
            e_frac = max(0.0, min(1.0, e_frac))

            px_start = margin_l + s_frac * plot_w
            px_end = margin_l + e_frac * plot_w

            # 创建霓虹蓝渐变笔刷
            grad = QLinearGradient(px_start, center_y, px_end, center_y)
            grad.setColorAt(0.0, QColor("#0ea5e9"))
            grad.setColorAt(1.0, QColor("#38bdf8"))
            
            # 覆盖绘制主轴
            pen_active = QPen(QBrush(grad), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_active)
            painter.drawLine(int(px_start), center_y, int(px_end), center_y)

            # 绘制左右端边界定位旗帜与数值标签
            pen_flag = QPen(QColor("#10b981"), 1.5, Qt.PenStyle.SolidLine)
            painter.setPen(pen_flag)
            painter.drawLine(int(px_start), center_y - 30, int(px_start), center_y)
            painter.drawLine(int(px_end), center_y - 30, int(px_end), center_y)

            # 起点桩号气泡
            painter.setPen(QColor("#10b981"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(int(px_start) - 25, center_y - 35, f"S: K102+{self.start_ch:.1f}")
            
            # 终点桩号气泡
            painter.setPen(QColor("#fb7185"))
            painter.drawText(int(px_end) - 25, center_y - 35, f"E: K102+{self.end_ch:.1f}")

            # 绘制中心区域名
            painter.setPen(QColor("#f8fafc"))
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            painter.drawText(int((px_start + px_end)/2) - 40, center_y - 12, self.section_name)

        # 水印
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(15, 30, "线性断面: K102里程轴投影匹配仪")

# ================= 2. 标段管理主控制面板 =================
class SectionMgrWidget(QWidget):
    # 标段与施工段段落管理。
    # 结合数据库读写，提供段落 CRUD 和几何填方工程量自动估算法。
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh_table()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. 顶部 HUD 显示仪表
        stats_panel = QHBoxLayout()
        self.hud_sections = self.create_glow_hud("累计登记施工标段数", "0", "SQLite 规划标段总数")
        self.hud_total_len = self.create_glow_hud("累计核定施工里程 (M)", "0.00", "累计开辟路堤轴线总长")
        self.hud_total_volume = self.create_glow_hud("累计预算填筑土石方 (M³)", "0.00", "土方实体体积立方基准")
        stats_panel.addWidget(self.hud_sections)
        stats_panel.addWidget(self.hud_total_len)
        stats_panel.addWidget(self.hud_total_volume)
        layout.addLayout(stats_panel)

        # 2. 中部核心区 (左侧录入与估算 + 中间列表表格 + 右侧击实图谱)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左边输入与几何土方量计算器侧边栏
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)

        lbl_sec1 = QLabel("⚙ 录入规划施工标段段落")
        lbl_sec1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_sec1)

        # 表单输入
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("施工标段名称 (例: 第二标段路基A段)")
        ctrl_layout.addWidget(self.txt_name)

        self.txt_start = QLineEdit()
        self.txt_start.setPlaceholderText("起始桩号绝对值 (m, 例: 150)")
        self.txt_start.textChanged.connect(self.on_chainage_input_changed)
        ctrl_layout.addWidget(self.txt_start)

        self.txt_end = QLineEdit()
        self.txt_end.setPlaceholderText("终止桩号绝对值 (m, 例: 650)")
        self.txt_end.textChanged.connect(self.on_chainage_input_changed)
        ctrl_layout.addWidget(self.txt_end)

        # 几何三维参数
        self.txt_width = QLineEdit()
        self.txt_width.setPlaceholderText("设计路基面幅宽 W (米, 默认: 22)")
        self.txt_width.textChanged.connect(self.on_chainage_input_changed)
        ctrl_layout.addWidget(self.txt_width)

        self.txt_thickness = QLineEdit()
        self.txt_thickness.setPlaceholderText("设计填筑标高厚度 H (米, 默认: 0.3)")
        self.txt_thickness.textChanged.connect(self.on_chainage_input_changed)
        ctrl_layout.addWidget(self.txt_thickness)

        # 表单功能按钮
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("💾 录入规划段")
        self.btn_add.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; padding: 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #34d399; }
        """)
        self.btn_add.clicked.connect(self.add_section)
        
        self.btn_del = QPushButton("🗑 注销段落")
        self.btn_del.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; padding: 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #f87171; }
        """)
        self.btn_del.clicked.connect(self.delete_section)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        ctrl_layout.addLayout(btn_layout)

        ctrl_layout.addSpacing(15)

        # 土石方方量自动计算面板 (力学模拟器)
        lbl_sec2 = QLabel("🧠 填方土石方量几何计算器")
        lbl_sec2.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")
        ctrl_layout.addWidget(lbl_sec2)
        
        lbl_calc_desc = QLabel("依据输入的起止桩号范围、幅宽及厚度，自动估算该工程规划所需的实体压实土石方量:")
        lbl_calc_desc.setWordWrap(True)
        lbl_calc_desc.setStyleSheet("color: #64748b; font-size: 9px; line-height: 12px; margin-bottom: 5px;")
        ctrl_layout.addWidget(lbl_calc_desc)

        # 计算器输出框
        self.lbl_volume_result = QLabel("路基预算土石方量: -- M³")
        self.lbl_volume_result.setStyleSheet("""
            color: #10b981; font-family: 'Consolas', monospace; font-size: 11.5px; font-weight: bold; 
            background-color: #0b0f19; border: 1px solid #1e293b; padding: 8px; border-radius: 4px; margin-top: 5px;
        """)
        ctrl_layout.addWidget(self.lbl_volume_result)

        # 控件统一样式
        self.setStyleSheet("""
            QLineEdit { background-color: #0f172a; color: white; border: 1px solid #475569; padding: 6px; border-radius: 4px; font-family: 'Consolas'; font-size: 11px; }
        """)

        ctrl_layout.addStretch()
        main_splitter.addWidget(ctrl_frame)

        # 中部：SQLite 数据表格
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["自增 ID", "施工段落名称", "起始标定 (m)", "结束标定 (m)"])
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
        linear_frame = QFrame()
        linear_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;")
        linear_layout = QVBoxLayout(linear_frame)
        linear_layout.setContentsMargins(10, 10, 10, 10)

        self.linear_canvas = NeonLinearSectionCanvas()
        linear_layout.addWidget(self.linear_canvas)

        main_splitter.addWidget(linear_frame)

        # 配置中幅宽度占比 2.2 : 4.8 : 3
        main_splitter.setSizes([220, 480, 300])
        layout.addWidget(main_splitter)

        # 底部系统日志终端
        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setPlaceholderText(">> 施工规划管理控制总线就绪...")
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

    # ================= 3. 施工标段数据库 CRUD 逻辑 =================
    def refresh_table(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id, section_name, start_chainage, end_chainage FROM sections")
            rows = cursor.fetchall()
            
            self.table.setRowCount(0)
            total_len = 0.0
            
            for r_idx, row_data in enumerate(rows):
                self.table.insertRow(r_idx)
                for c_idx, val in enumerate(row_data):
                    self.table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
                
                # 累加里程轴规划长度
                length = abs(row_data[3] - row_data[2])
                total_len += length
                
            # 刷新 HUD 数据看板
            self.hud_sections.lbl_val.setText(str(len(rows)))
            self.hud_total_len.lbl_val.setText(f"{total_len:.2f}")
            
            # 自动拟合大坝/填方体积 (W=22m, H=0.3m 基准)
            total_vol = total_len * 22.0 * 0.3
            self.hud_total_volume.lbl_val.setText(f"{total_vol:.2f}")
            
        except Exception as e:
            self.write_log(f"数据载入错误: {str(e)}")
        finally:
            conn.close()

    def add_section(self):
        name = self.txt_name.text().strip()
        start = self.txt_start.text().strip()
        end = self.txt_end.text().strip()
        
        if not name or not start or not end:
            QMessageBox.warning(self, "校验提示", "标段名称、起止桩号不允许为空。")
            return
            
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO sections (section_name, start_chainage, end_chainage, target_density) VALUES (?, ?, ?, ?)",
                           (name, float(start), float(end), 96.0))
            conn.commit()
            conn.close()
            
            self.write_log(f"新规划标段入库: '{name}' (K102+{start}m ~ K102+{end}m)")
            
            # 如果主窗体支持动态下拉，触发刷新
            parent_main = self.parent()
            while parent_main is not None:
                if hasattr(parent_main, 'nav_list'):
                    # 寻找历史溯源模块更新下拉目录
                    history_view = parent_main.work_stack.widget(4)
                    if hasattr(history_view, 'load_combobox_directories'):
                        history_view.load_combobox_directories()
                    break
                parent_main = parent_main.parent()

            self.refresh_table()
            self.txt_name.clear()
            self.txt_start.clear()
            self.txt_end.clear()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "数据库冲突", "登记失败：此标段规划命名已存在于数据库中。")
        except Exception as e:
            QMessageBox.critical(self, "系统报错", f"写入错误: {str(e)}")

    def delete_section(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "操作提示", "请先在列表中选中需要物理注销的施工规划。")
            return
            
        db_id = self.table.item(curr_row, 0).text()
        sect_name = self.table.item(curr_row, 1).text()
        
        reply = QMessageBox.question(self, "标段规划撤销", f"确定彻底在规划库中删除并注销标段 '{sect_name}' 吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM sections WHERE id=?", (db_id,))
                conn.commit()
                self.write_log(f"标段规划注销成功: {sect_name} (ID: {db_id})")
                
                # 级联更新历史下拉框
                parent_main = self.parent()
                while parent_main is not None:
                    if hasattr(parent_main, 'nav_list'):
                        history_view = parent_main.work_stack.widget(4)
                        if hasattr(history_view, 'load_combobox_directories'):
                            history_view.load_combobox_directories()
                        break
                    parent_main = parent_main.parent()

                self.refresh_table()
                self.linear_canvas.clear_canvas()
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))
            finally:
                conn.close()

    # ================= 4. 高阶交互：列表联动里程甘特图重绘 =================
    def on_table_selection_changed(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            return
            
        name = self.table.item(curr_row, 1).text()
        start = float(self.table.item(curr_row, 2).text())
        end = float(self.table.item(curr_row, 3).text())
        
        # 联动物理进度图
        self.linear_canvas.load_section_parameters(name, start, end)
        self.write_log(f"规划里程轴空间定位: 公路 K102里程轴重新匹配至 '{name}' 覆盖带")

        # 辅助填充到体积计算输入框，省去手动输入
        self.txt_start.setText(f"{start:.0f}")
        self.txt_end.setText(f"{end:.0f}")

    # ================= 5. 土石方几何工程量自动估算算法 =================
    def on_chainage_input_changed(self):
        s_text = self.txt_start.text().strip()
        e_text = self.txt_end.text().strip()
        w_text = self.txt_width.text().strip()
        h_text = self.txt_thickness.text().strip()
        
        if not s_text or not e_text:
            self.lbl_volume_result.setText("路基预算土石方量: -- M³")
            return
            
        try:
            start_ch = float(s_text)
            end_ch = float(e_text)
            
            # 幅宽默认 22m, 填筑厚度默认 0.3m
            width = float(w_text) if w_text else 22.0
            thickness = float(h_text) if h_text else 0.3
            
            length = abs(end_ch - start_ch)
            
            # V = L * W * H
            volume = length * width * thickness
            
            self.lbl_volume_result.setText(f"路基预算土石方量: {volume:.1f} M³")
        except ValueError:
            pass

def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime('%H:%M:%S')