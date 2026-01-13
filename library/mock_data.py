# SPDX-License-Identifier: GPL-3.0-or-later
import library.config as config

class MockDataProvider:
    """Provides mock sensor data for the theme editor preview."""
    
    @staticmethod
    def populate():
        """Populate config.STATS_VALUES and config.STATS_RAW with mock data."""
        # Use a base set of values that cover most sensor paths
        mock_values = {
            "CPU_PERCENTAGE": "42%",
            "CPU_TEMPERATURE": "55°C",
            "CPU_FREQUENCY": "4.20 GHz",
            "CPU_LOAD_LOAD1": "1.2",
            "CPU_LOAD_LOAD5": "1.0",
            "CPU_LOAD_LOAD15": "0.8",
            
            "GPU_PERCENTAGE": "68%",
            "GPU_TEMPERATURE": "62°C",
            "GPU_MEMORY_USED": "4096 M",
            "GPU_MEMORY_TOTAL": "8192 M",
            "GPU_MEMORY_FREE": "4096 M",
            "GPU_MEMORY_PERCENTAGE": "50%",
            "GPU_FPS": "144",
            
            "MEMORY_PERCENTAGE": "45%",
            "MEMORY_USED": "16384 M",
            "MEMORY_TOTAL": "32768 M",
            "MEMORY_FREE": "16384 M",
            "MEMORY_VIRTUAL_PERCENTAGE": "48%",
            "MEMORY_VIRTUAL_USED": "18000 M",
            "MEMORY_VIRTUAL_TOTAL": "32000 M",
            "MEMORY_SWAP_PERCENTAGE": "10%",
            
            "DISK_PERCENTAGE": "33%",
            "DISK_USED": "333 G",
            "DISK_TOTAL": "1000 G",
            "DISK_FREE": "667 G",
            
            "NET_DOWNLOAD_RATE": "1.2 MB/s",
            "NET_UPLOAD_RATE": "0.5 MB/s",
            "NET_DOWNLOADED": "100 GB",
            "NET_UPLOADED": "20 GB",
            
            "DATE_DAY": "Monday, Jan 12",
            "DATE_HOUR": "17:45:00",
            
            "UPTIME_FORMATTED": "2 days, 15:33:10",
            "UPTIME_SECONDS": "228790",
            
            "WEATHER_TEMPERATURE": "22°C",
            "WEATHER_TEMPERATURE_FELT": "24°C",
            "WEATHER_HUMIDITY": "60%",
            "WEATHER_DESCRIPTION": "Partly Cloudy",
            "WEATHER_UPDATE_TIME": "17:40",
            
            "PING_LATENCY": "15 ms",
            "PING_PERCENTAGE": "0%",
        }

        # Handle RAW values automatically
        stats_raw = {}
        for k, v in mock_values.items():
            # Use the string value for STATS_VALUES
            config.STATS_VALUES[k] = v
            
            # Try to extract a numeric value for STATS_RAW
            raw_val = v
            if isinstance(v, str):
                # Remove common units
                for unit in ["%", "°C", " GHz", " M", " G", " MB/s", " ms", " FPS", " GB"]:
                    raw_val = raw_val.replace(unit, "")
                try:
                    raw_val = float(raw_val.strip())
                except ValueError:
                    pass
            stats_raw[k] = raw_val
            config.STATS_RAW[k] = raw_val

        # Add dot-notation versions for everything
        all_keys = list(config.STATS_VALUES.keys())
        for k in all_keys:
            if "_" in k:
                dot_key = k.replace("_", ".")
                config.STATS_VALUES[dot_key] = config.STATS_VALUES[k]
                if k in stats_raw:
                    config.STATS_RAW[dot_key] = stats_raw[k]
        
        # Add some specific multi-level dots that might be used
        # e.g. MEMORY_VIRTUAL_PERCENTAGE -> MEMORY.VIRTUAL.PERCENTAGE
        for k in all_keys:
             if "_VIRTUAL_" in k:
                 dot_key = k.replace("_VIRTUAL_", ".VIRTUAL.")
                 config.STATS_VALUES[dot_key] = config.STATS_VALUES[k]
                 if k in stats_raw:
                     config.STATS_RAW[dot_key] = stats_raw[k]
             if "_SWAP_" in k:
                 dot_key = k.replace("_SWAP_", ".SWAP.")
                 config.STATS_VALUES[dot_key] = config.STATS_VALUES[k]
                 if k in stats_raw:
                     config.STATS_RAW[dot_key] = stats_raw[k]

        # Ensure UPTIME.SECONDS_RAW etc match the expected format
        for k, v in stats_raw.items():
            config.STATS_VALUES[f"{k}_RAW"] = str(v)
            if "_" in k:
                dot_key = k.replace("_", ".")
                config.STATS_VALUES[f"{dot_key}_RAW"] = str(v)

