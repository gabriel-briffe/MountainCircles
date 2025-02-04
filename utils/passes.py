import pandas as pd
import os

def collect_and_merge_csv_files(root_folder):
    """
    Collect and merge all CSV files containing mountain pass data.
    
    Args:
    root_folder (str): Path to the root folder containing the CSV files
    """
    # List to store all dataframes
    dfs = []
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith('.csv') and 'passes' in file.lower():
                file_path = os.path.join(root, file)
                try:
                    df = pd.read_csv(file_path)
                    dfs.append(df)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    if not dfs:
        raise ValueError("No valid CSV files found")
    
    # Merge all dataframes
    merged_df = pd.concat(dfs, ignore_index=True)
    
    # Remove duplicates based on coordinates
    merged_df = merged_df.drop_duplicates(subset=['x', 'y'])
    
    # Save the merged data
    output_path = os.path.join(root_folder, 'merged_passes.csv')
    merged_df.to_csv(output_path, index=False)
    print(f"Merged data saved to {output_path}")

if __name__ == "__main__":
    root_folder = "./results"
    collect_and_merge_csv_files(root_folder)