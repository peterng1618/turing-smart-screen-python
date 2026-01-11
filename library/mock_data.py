# SPDX-License-Identifier: GPL-3.0-or-later
import library.config as config
import datetime

class MockDataProvider:
    """Provides mock sensor data for the theme editor preview."""
    
    @staticmethod
    def populate():
        """Populate config.STATS_VALUES and config.STATS_RAW with mock data."""
        mock_values = {
            "CPU_PERCENTAGE": "42%",
            "CPU_PERCENTAGE_RAW": "42",
            "CPU_TEMPERATURE": "55°C",
            "CPU_TEMPERATURE_RAW": "55",
            "CPU_FREQUENCY": "4.20 GHz",
            "CPU_FREQUENCY_RAW": "4200",
            
            "GPU_PERCENTAGE": "68%",
            "GPU_PERCENTAGE_RAW": "68",
            "GPU_TEMPERATURE": "62°C",
            "GPU_TEMPERATURE_RAW": "62",
            "GPU_MEMORY_USED": "4096 M",
            "GPU_MEMORY_USED_RAW": "4096",
            "GPU_MEMORY_TOTAL": "8192 M",
            "GPU_MEMORY_TOTAL_RAW": "8192",
            "GPU_FPS": "144 FPS",
            "GPU_FPS_RAW": "144",
            
            # Memory - with aliases for MEMORY_ prefix
            "MEM_VIRTUAL_PERCENT": "45%",
            "MEM_VIRTUAL_PERCENT_RAW": "45",
            "MEM_VIRTUAL_USED": "16384 M",
            "MEM_VIRTUAL_USED_RAW": "16384",
            "MEM_VIRTUAL_TOTAL": "32768 M",
            "MEM_VIRTUAL_TOTAL_RAW": "32768",
            "MEMORY_PERCENTAGE": "45%",  # Alias
            "MEMORY_PERCENTAGE_RAW": "45",
            
            # Disk - with aliases
            "DISK_USED_PERCENT": "33%",
            "DISK_USED_PERCENT_RAW": "33",
            "DISK_USED": "333 G",
            "DISK_USED_RAW": "333",
            "DISK_TOTAL": "1000 G",
            "DISK_TOTAL_RAW": "1000",
            "DISK_PERCENTAGE": "33%",  # Alias
            "DISK_PERCENTAGE_RAW": "33",
            
            # Network - with aliases
            "NET_DOWNLOAD_RATE": "1.2 MB/s",
            "NET_DOWNLOAD_RATE_RAW": "1200000",
            "NET_UPLOAD_RATE": "0.5 MB/s",
            "NET_UPLOAD_RATE_RAW": "500000",
            "NET_PERCENTAGE": "25%",  # Alias (network utilization)
            "NET_PERCENTAGE_RAW": "25",
            
            "DATE_DAY": "Monday, Jan 12",
            "DATE_HOUR": "17:45:00",
            "DATE_PERCENTAGE": "50%",  # Placeholder
            
            "UPTIME_FORMATTED": "2:15:33",
            "UPTIME_SECONDS": "8133",
            "UPTIME_SECONDS_RAW": "8133",
            "UPTIME_PERCENTAGE": "100%",  # Placeholder
            
            "WEATHER_TEMP": "22°C",
            "WEATHER_DESC": "Partly Cloudy",
            "WEATHER_PERCENTAGE": "60%",  # Placeholder (humidity)
            
            "PING_PERCENTAGE": "10%",  # Placeholder
        }
        
        config.STATS_VALUES.update(mock_values)
        
        # Populate RAW values as matching types (int/float)
        for k, v in mock_values.items():
            if k.endswith("_RAW"):
                sensor_base = k[:-4]
                try:
                    config.STATS_RAW[sensor_base] = float(v.strip())
                except ValueError:
                    config.STATS_RAW[sensor_base] = v
