# core/algorithm.py
import numpy as np

class CompactionEngine:
    @staticmethod
    def calculate_cmv(time_series: np.ndarray, sampling_rate: float) -> float:
        """
        利用振动加速度信号频谱分析计算 CMV (Compaction Meter Value)
        """
        n = len(time_series)
        if n < 128:
            return 0.0
            
        fft_values = np.abs(np.fft.rfft(time_series))
        frequencies = np.fft.rfftfreq(n, d=1.0/sampling_rate)
        
        valid_idx = np.where((frequencies >= 20) & (frequencies <= 60))[0]
        if len(valid_idx) == 0:
            return 0.0
            
        fundamental_idx = valid_idx[np.argmax(fft_values[valid_idx])]
        f_val = frequencies[fundamental_idx]
        
        harmonic_target = 2.0 * f_val
        harmonic_idx = np.argmin(np.abs(frequencies - harmonic_target))
        
        amplitude_fundamental = fft_values[fundamental_idx]
        amplitude_harmonic = fft_values[harmonic_idx]
        
        if amplitude_fundamental == 0:
            return 0.0
            
        cmv = 300.0 * (amplitude_harmonic / amplitude_fundamental)
        return float(np.clip(cmv, 0, 150))

    @staticmethod
    def detect_weak_zones(points: list, window_size: float = 12.0, threshold_z: float = -1.5) -> list:
        """
        空间滑动窗口异常检测算法：
        points 格式为：[(x, y, value, id), ...]
        """
        if not points:
            return []
            
        anomalies = []
        data_arr = np.array([(p[0], p[1], p[2]) for p in points])
        
        for i, (x, y, val) in enumerate(data_arr):
            # 采用欧氏距离筛选空间物理局域网格点
            distances = np.linalg.norm(data_arr[:, :2] - np.array([x, y]), axis=1)
            neighbors = data_arr[distances <= window_size]
            
            if len(neighbors) < 3:
                continue
                
            local_vals = neighbors[:, 2]
            local_mean = np.mean(local_vals)
            local_std = np.std(local_vals)
            
            if local_std < 0.01:
                continue
                
            z_score = (val - local_mean) / local_std
            if z_score < threshold_z:
                anomalies.append(points[i])
                
        return anomalies