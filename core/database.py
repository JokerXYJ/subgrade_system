# core/database.py
import sqlite3
import os

DB_PATH = "subgrade_data.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def initialize_database():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    
    # 2. 标段段落表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_name TEXT UNIQUE NOT NULL,
            start_chainage REAL,
            end_chainage REAL,
            target_density REAL
        )
    """)
    
    # 3. 压实机具表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS machinery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_code TEXT UNIQUE NOT NULL,
            weight REAL,
            vibration_freq REAL,
            amplitude REAL
        )
    """)
    
    # 4. 土质参数与标准击实表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS soil_standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            soil_type TEXT UNIQUE NOT NULL,
            max_dry_density REAL,
            optimum_moisture REAL
        )
    """)
    
    # 5. 压实监测原始数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            section_id INTEGER,
            machine_id INTEGER,
            coordinate_x REAL,
            coordinate_y REAL,
            elevation REAL,
            speed REAL,
            frequency REAL,
            amplitude REAL,
            acceleration_fundamental REAL,
            acceleration_harmonic REAL,
            cmv REAL,
            FOREIGN KEY(section_id) REFERENCES sections(id),
            FOREIGN KEY(machine_id) REFERENCES machinery(id)
        )
    """)
    
    conn.commit()
    conn.close()