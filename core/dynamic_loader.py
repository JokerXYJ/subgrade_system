# core/dynamic_loader.py
import importlib
import sys

class ModuleLoader:
    _loaded_modules = {}

    @classmethod
    def load_module_widget(cls, module_name: str, class_name: str, parent=None):
        """
        根据模块名称和类名进行动态加载。
        如果模块已存在于内存中，则强制执行 reload。
        """
        full_module_name = f"modules.{module_name}"
        try:
            if full_module_name in sys.modules:
                module = importlib.reload(sys.modules[full_module_name])
            else:
                module = importlib.import_module(full_module_name)
                
            cls._loaded_modules[full_module_name] = module
            target_class = getattr(module, class_name)
            return target_class(parent=parent)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox, QWidget, QVBoxLayout, QLabel
            err_widget = QWidget(parent)
            layout = QVBoxLayout(err_widget)
            layout.addWidget(QLabel(f"模块加载失败: {module_name}\n错误信息: {str(e)}"))
            return err_widget