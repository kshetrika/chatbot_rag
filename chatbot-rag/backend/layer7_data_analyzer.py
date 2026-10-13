"""
LAYER 7 - Data Analyzer
Answers questions about uploaded datasets from Kaggle/Local
"""

import pandas as pd
from layer6_csv_processor import csv_processor

loaded_datasets = {}


def load_dataset(filepath, filename):
    df, error = csv_processor.read_file(filepath)
    if error:
        return None, error
    loaded_datasets[filename] = df
    return df, None


def is_data_question(question):
    keywords = [
        'how many', 'what is', 'show', 'average', 'total', 'sum', 'maximum',
        'minimum', 'count', 'list', 'distribution', 'top', 'highest', 'lowest',
        'dataset', 'column', 'row', 'records', 'statistics', 'analysis'
    ]
    return any(keyword in question.lower() for keyword in keywords)


def answer_data_question(question, filename):
    if filename not in loaded_datasets:
        return "Dataset not loaded"
    
    df = loaded_datasets[filename]
    q = question.lower()
    
    try:
        if 'how many' in q and ('row' in q or 'record' in q):
            return f"**Total records in dataset:** {len(df)}"
        
        if 'how many' in q and 'column' in q:
            return f"**Total columns:** {len(df.columns)}\n\n**Column names:** {', '.join(df.columns)}"
        
        if 'show' in q and ('first' in q or 'top' in q):
            rows = 5
            return f"**First {rows} records:**\n\n{df.head(rows).to_string()}"
        
        if 'average' in q or 'mean' in q:
            for col in df.columns:
                if col.lower() in q:
                    if df[col].dtype in ['int64', 'float64']:
                        avg = df[col].mean()
                        return f"**Average {col}:** {avg:.2f}"
        
        if 'sum' in q or 'total' in q:
            for col in df.columns:
                if col.lower() in q:
                    if df[col].dtype in ['int64', 'float64']:
                        total = df[col].sum()
                        return f"**Total {col}:** {total:.2f}"
        
        if 'maximum' in q or 'highest' in q or 'max' in q:
            for col in df.columns:
                if col.lower() in q:
                    if df[col].dtype in ['int64', 'float64']:
                        max_val = df[col].max()
                        return f"**Highest {col}:** {max_val:.2f}"
        
        if 'minimum' in q or 'lowest' in q or 'min' in q:
            for col in df.columns:
                if col.lower() in q:
                    if df[col].dtype in ['int64', 'float64']:
                        min_val = df[col].min()
                        return f"**Lowest {col}:** {min_val:.2f}"
        
        if 'unique' in q or 'distinct' in q:
            for col in df.columns:
                if col.lower() in q:
                    count = df[col].nunique()
                    return f"**Unique {col} values:** {count}"
        
        if 'column' in q and ('show' in q or 'list' in q or 'what' in q):
            return f"**All columns in dataset:**\n{', '.join(df.columns)}"
        
        if 'info' in q or 'summary' in q or 'overview' in q:
            summary = csv_processor.get_file_summary(df)
            stats = csv_processor.get_column_statistics(df)
            response = f"""**Dataset Summary:**
- Records: {summary['rows']}
- Columns: {summary['columns']}
- Size: {summary['file_size']}

**Column Statistics:**
"""
            for col, stat in list(stats.items())[:5]:
                if stat['type'] == 'numeric':
                    response += f"\n- **{col}** (numeric): Min={stat['min']:.2f}, Max={stat['max']:.2f}, Mean={stat['mean']:.2f}"
                else:
                    response += f"\n- **{col}** (text): {stat['unique_values']} unique values"
            return response
        
        return "I could not understand the question. Try: 'How many rows?', 'What columns?', 'Show first 5 records', 'Average [column]', 'Maximum [column]'"
    
    except Exception as e:
        return f"Error analyzing data: {str(e)}"
