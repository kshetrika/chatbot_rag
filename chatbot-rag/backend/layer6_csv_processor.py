"""
LAYER 6 - CSV/Dataset File Processor
Processes uploaded files for analysis
"""

import pandas as pd
import os
from pathlib import Path


class CSVProcessor:
    def __init__(self):
        self.upload_folder = "./uploaded_files"
        self.processed_folder = "./processed_data"
        Path(self.upload_folder).mkdir(exist_ok=True)
        Path(self.processed_folder).mkdir(exist_ok=True)
    
    def save_uploaded_file(self, file):
        filepath = os.path.join(self.upload_folder, file.filename)
        file.save(filepath)
        return filepath
    
    def read_file(self, filepath):
        try:
            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath)
            elif filepath.endswith('.xlsx') or filepath.endswith('.xls'):
                df = pd.read_excel(filepath)
            else:
                return None, "Unsupported file format. Use CSV or XLSX"
            return df, None
        except Exception as e:
            return None, f"Error reading file: {str(e)}"
    
    def get_file_summary(self, df):
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "file_size": f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
        }
    
    def get_column_statistics(self, df):
        stats = {}
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                stats[col] = {
                    "type": "numeric",
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median()),
                    "std": float(df[col].std())
                }
            else:
                stats[col] = {
                    "type": "categorical",
                    "unique_values": int(df[col].nunique()),
                    "most_common": str(df[col].mode()[0]) if len(df[col].mode()) > 0 else "N/A"
                }
        return stats


csv_processor = CSVProcessor()
