#!/usr/bin/env python3
"""
Sistema de límites por plataforma para maximizar aplicaciones sin ser bloqueado
"""

from datetime import datetime, date
import sqlite3
import random
from typing import Dict, List, Optional

class PlatformLimitManager:
    """Gestiona los límites diarios por plataforma"""
    
    # LÍMITES CONSERVADORES POR PLATAFORMA (ajustables)
    DEFAULT_LIMITS = {
        'linkedin': 100,        # 80-100 es seguro
        'dice': 150,
        'greenhouse': 150,      
        'tecnoempleo': 50,     # 50 conservador
        'wellfound': 100,      # Más permisivo
        'remotive': 200,       # Agregador, redirige
        'nodesk': 100,         # Agregador
        'remote100k': 100,     # Agregador
        'hiringcafe': 100,     # Agregador
        'other': 150           # Otros sitios
    }
    
    # PAUSAS RECOMENDADAS ENTRE APLICACIONES (segundos)
    PAUSAS = {
        'linkedin':    {'min': 10, 'max': 15},
        'indeed':      {'min': 10, 'max': 15},
        'greenhouse':    {'min': 10, 'max': 15},
        'tecnoempleo': {'min': 10, 'max': 15},
        'wellfound':   {'min': 10, 'max': 15},
        'remotive':    {'min': 10, 'max': 15},
        'default':     {'min': 10, 'max': 15},
    }
    
    def __init__(self, db_path: str = "applications.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_tracking()
        self.today = date.today().isoformat()
        
    def _init_tracking(self):
        """Inicializa tabla de seguimiento de límites"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS platform_daily_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                platform TEXT,
                count INTEGER DEFAULT 0,
                last_applied TEXT,
                UNIQUE(date, platform)
            )
        ''')
        self.conn.commit()
    
    def get_remaining(self, platform: str) -> int:
        """Obtiene cuántas aplicaciones quedan hoy para esta plataforma"""
        limit = self.DEFAULT_LIMITS.get(platform, self.DEFAULT_LIMITS['other'])
        
        self.cursor.execute('''
            SELECT count FROM platform_daily_usage
            WHERE date = ? AND platform = ?
        ''', (self.today, platform))
        
        row = self.cursor.fetchone()
        used = row[0] if row else 0
        
        remaining = limit - used
        return max(0, remaining)
    
    def can_apply(self, platform: str) -> bool:
        """Verifica si aún podemos aplicar en esta plataforma hoy"""
        return self.get_remaining(platform) > 0
    
    def register_application(self, platform: str):
        """Registra una aplicación en la plataforma"""
        self.cursor.execute('''
            INSERT INTO platform_daily_usage (date, platform, count, last_applied)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(date, platform) DO UPDATE SET
                count = count + 1,
                last_applied = excluded.last_applied
        ''', (self.today, platform, datetime.now().isoformat()))
        self.conn.commit()
        
        remaining = self.get_remaining(platform)
        print(f"   📊 {platform.capitalize()}: {remaining} aplicaciones restantes hoy")
    
    def get_pause_time(self, platform: str) -> int:
        """Obtiene tiempo de pausa recomendado para la plataforma"""
        pause_config = self.PAUSAS.get(platform, self.PAUSAS['default'])
        return random.randint(pause_config['min'], pause_config['max'])
    
    def get_daily_summary(self) -> Dict:
        """Obtiene resumen del día"""
        self.cursor.execute('''
            SELECT platform, count FROM platform_daily_usage
            WHERE date = ?
            ORDER BY count DESC
        ''', (self.today,))
        
        rows = self.cursor.fetchall()
        
        summary = {
            'date': self.today,
            'total': sum(row[1] for row in rows),
            'by_platform': {row[0]: row[1] for row in rows},
            'limits': self.DEFAULT_LIMITS
        }
        
        # Calcular porcentajes
        summary['percentages'] = {
            platform: {
                'used': summary['by_platform'].get(platform, 0),
                'limit': limit,
                'remaining': limit - summary['by_platform'].get(platform, 0)
            }
            for platform, limit in self.DEFAULT_LIMITS.items()
        }
        
        return summary

    def reset_platform_limit(self, platform: str):
        """Reset limit for a specific platform for today"""
        self.cursor.execute('DELETE FROM platform_daily_usage WHERE date = ? AND platform = ?', (self.today, platform))
        self.conn.commit()
        print(f"   🔄 Reset {platform} limits for {self.today}")
    
    def close(self):
        """Cierra conexión"""
        if self.conn:
            self.conn.close()
