import os
import csv
from collections import defaultdict

def collect_and_merge_csv_files(root_folder):
    # Dictionary to hold unique entries
    all_passes = defaultdict(dict)

    # Traverse through each subfolder in the root folder
    for subdir, _, files in os.walk(root_folder):
        # Skip the "airfields" folder
        if "airfields" in subdir:
            continue
        
        # Look for 'mountain_passes.csv' in each subfolder
        if 'mountain_passes.csv' in files:
            csv_path = os.path.join(subdir, 'mountain_passes.csv')
            with open(csv_path, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Create a key from name, x, and y for uniqueness
                    key = (row['name'], row['x'], row['y'])
                    # Use the first occurrence of each pass (based on name, x, y)
                    if key not in all_passes:
                        all_passes[key] = {'name': row['name'], 'x': row['x'], 'y': row['y']}

    # Write the merged data to a new CSV file at the root
    output_file = os.path.join(root_folder, 'all_mountain_passes.csv')
    with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=['name', 'x', 'y'])
        writer.writeheader()
        for pass_data in all_passes.values():
            writer.writerow(pass_data)

    print(f"Merging complete. Result written to {output_file}")
    print(f"Total unique mountain passes: {len(all_passes)}")

# Assuming the root directory is where this script is run from
root_folder = 'results/everything'
collect_and_merge_csv_files(root_folder)