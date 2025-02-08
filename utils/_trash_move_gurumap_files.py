import os
import shutil

def copy_airfield_files(base_dir, singles_dir):
    # Ensure singles directory exists
    if not os.path.exists(singles_dir):
        os.makedirs(singles_dir)

    # Walk through all directories in the base directory except "airfields" and "singles"
    for root, dirs, files in os.walk(base_dir):
        if 'airfields' not in root and 'singles' not in root:
            for file in files:
                if file.endswith('_airfields.geojson') or file.endswith('_airfields.mapcss'):
                    # Extract airfield name from filename
                    airfield_name = file.split('_')[0]
                    
                    # Create the destination directory if it doesn't exist
                    airfield_dest_dir = os.path.normpath(os.path.join(singles_dir, airfield_name))
                    if not os.path.exists(airfield_dest_dir):
                        os.makedirs(airfield_dest_dir)
                    
                    # Construct source and destination paths
                    src_path = os.path.normpath(os.path.join(root, file))
                    dest_path = os.path.normpath(os.path.join(airfield_dest_dir, file.split('_')[0] + os.path.splitext(file)[1]))
                    
                    # Copy the file
                    shutil.copy2(src_path, dest_path)  # copy2 preserves metadata
                    print(f"Copied {src_path} to {dest_path}")

# Assuming you're running this script from within the 'everything' directory
base_dir = os.path.normpath('.')    
singles_dir = os.path.normpath('singles')

copy_airfield_files(base_dir, singles_dir)