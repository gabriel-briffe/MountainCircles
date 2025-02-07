import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import sys
import yaml
import pandas as pd
from src.config import Config
import launch
import subprocess
import multiprocessing
from utils.cupConvert import convert_coord
import webbrowser  # Add this import if not already present


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class MountainCirclesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mountain Circles")
        self.root.resizable(True, True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)
        
        # Create tabs
        self.run_tab = ttk.Frame(self.notebook)
        self.download_tab = ttk.Frame(self.notebook)
        self.utilities_tab = ttk.Frame(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(self.download_tab, text='Download')
        self.notebook.add(self.run_tab, text='Run')
        self.notebook.add(self.utilities_tab, text='Utilities')
        
        # Setup tabs
        self.setup_download_tab()
        self.setup_run_tab()
        self.setup_utilities_tab()



    def setup_download_tab(self):
        """Setup the Download tab without scroll functionality"""
        # Create a main frame for the download tab that fills the tab entirely
        main_frame = ttk.Frame(self.download_tab)
        main_frame.pack(expand=True, fill="both")
        
        # Create a content frame and center it within the main frame
        content_frame = ttk.Frame(main_frame)
        content_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        # Add label with the text
        label = ttk.Label(content_frame, text="Download data files and directory structure to start your project:")
        label.pack(pady=10)
        
        # Add the download button which opens the system browser to a web address
        button = ttk.Button(content_frame, text="Download Now", command=self.open_download_page)
        button.pack(pady=10)


    def setup_run_tab(self):
        """Setup the Run tab with a simple layout using only frames."""
        # Create a main frame that fills the Run tab
        main_frame = ttk.Frame(self.run_tab, padding="5")
        main_frame.pack(expand=True, fill="both")
        main_frame.pack_propagate(False)
        
        # Initialize variables with empty values
        self.name = tk.StringVar(value="")
        self.airfield_path = tk.StringVar(value="")
        self.topo_path = tk.StringVar(value="")
        self.result_path = tk.StringVar(value="")
        self.glide_ratio = tk.StringVar(value="")
        self.ground_clearance = tk.StringVar(value="")
        self.circuit_height = tk.StringVar(value="")
        self.max_altitude = tk.StringVar(value="")
        self.gurumaps = tk.BooleanVar(value=False)
        self.export_passes = tk.BooleanVar(value=False)
        self.reset_results = tk.BooleanVar(value=False)
        self.clean_temporary_files = tk.BooleanVar(value=False)
        
        #------------------------------------------------------------

        # Create configuration frame at the top
        config_frame = ttk.LabelFrame(main_frame, padding="5")
        # config_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        config_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Get list of YAML files and set up the config dropdown
        self.yaml_files = [f for f in os.listdir('.') if f.endswith('.yaml')]
        
        # Add Config dropdown and refresh button
        ttk.Label(config_frame, text="Select Config:").grid(row=0, column=0, padx=5, sticky="ew")
        self.config_dropdown = ttk.Combobox(config_frame, values=self.yaml_files, width=30)
        self.config_dropdown.grid(row=0, column=1, padx=5, sticky="ew")
        self.config_dropdown.bind('<<ComboboxSelected>>', self.load_selected_config)
        
        # Set default selection to the first available value if any exist
        if self.yaml_files:
            self.config_dropdown.current(0)
            self.load_selected_config(self)
        
        ttk.Button(config_frame, text="Refresh List", command=self.refresh_yaml_list).grid(row=0, column=2, padx=5, sticky="ew")
        
        # Configure grid columns to spread evenly
        config_frame.grid_columnconfigure(0, weight=0)
        config_frame.grid_columnconfigure(1, weight=2)
        config_frame.grid_columnconfigure(2, weight=0)
        
        #-------------------------------------------------------------

        # Create parameter input frame
        param_frame = ttk.LabelFrame(main_frame, text="Config Parameters :", padding="5")
        param_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Config name and Save button
        ttk.Label(param_frame, text="Config name:").grid(row=1, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.name).grid(row=1, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Save Config", command=self.save_config).grid(row=1, column=2)
        
        # Airfield file selection
        ttk.Label(param_frame, text="Airfield File:").grid(row=2, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.airfield_path).grid(row=2, column=1, padx=5, sticky="ew")
        airfield_buttons_frame = ttk.Frame(param_frame)
        airfield_buttons_frame.grid(row=2, column=2, sticky="w")
        ttk.Button(airfield_buttons_frame, text="Browse", command=lambda: self.browse_file("Airfield File", self.airfield_path)).grid(row=0, column=0, padx=2)
        ttk.Button(airfield_buttons_frame, text="Open/edit", command=self.open_airfield_file).grid(row=0, column=1, padx=2)
        
        # Topography file selection
        ttk.Label(param_frame, text="Topography File:").grid(row=3, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.topo_path).grid(row=3, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_file("Topography File", self.topo_path)).grid(row=3, column=2)
        
        # Result folder selection
        ttk.Label(param_frame, text="Result Folder:").grid(row=4, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.result_path).grid(row=4, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_directory("Results Folder", self.result_path)).grid(row=4, column=2)
        
        # Glide Parameters Section
        ttk.Label(param_frame, text="Glide Parameters", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky="w", pady=(15,5))
        
        # Glide ratio
        ttk.Label(param_frame, text="Glide Ratio:").grid(row=6, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.glide_ratio, width=10).grid(row=6, column=1, sticky="w", padx=5)
        
        # Ground clearance
        ttk.Label(param_frame, text="Ground Clearance (m):").grid(row=7, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.ground_clearance, width=10).grid(row=7, column=1, sticky="w", padx=5)
        
        # Circuit height
        ttk.Label(param_frame, text="Circuit Height (m):").grid(row=8, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.circuit_height, width=10).grid(row=8, column=1, sticky="w", padx=5)
        
        # Max altitude
        ttk.Label(param_frame, text="Max Altitude (m):").grid(row=9, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.max_altitude, width=10).grid(row=9, column=1, sticky="w", padx=5)
        
        # Additional Options Section
        ttk.Label(param_frame, text="Additional Options", font=('Arial', 10, 'bold')).grid(row=10, column=0, sticky="w", pady=(15,5))
        
        # Checkboxes
        ttk.Checkbutton(param_frame, text="Wipe result folder", variable=self.reset_results).grid(row=11, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Generate data files for Guru Maps", variable=self.gurumaps).grid(row=12, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Create mountain passes files", variable=self.export_passes).grid(row=13, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Clean temporary files", variable=self.clean_temporary_files).grid(row=14, column=0, sticky="w")
        
        param_frame.grid_columnconfigure(1, weight="1")
        
        # Control buttons frame
        control_btn_frame = ttk.Frame(main_frame)
        control_btn_frame.grid(row=15, column=0, columnspan=3, pady=10)
        ttk.Button(control_btn_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)

        self.run_button = ttk.Button(control_btn_frame, text="Run Processing", command=self.run_processing)
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        self.open_results_button = ttk.Button(control_btn_frame, text="Open Results Folder", command=self.open_results_folder)
        self.open_results_button.pack(side=tk.LEFT, padx=5)
        
        # Status display area
        ttk.Label(main_frame, text="Status:", font=('Arial', 10, 'bold')).grid(row=16, column=0, sticky="w", pady=5)
        self.status_text = tk.Text(main_frame)
        self.status_text.grid(row=17, column=0, columnspan=3, pady=5, sticky="nsew")
        scroller = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        scroller.grid(row=17, column=3, sticky="ns")
        self.status_text['yscrollcommand'] = scroller.set

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(17, weight=1)






    def setup_utilities_tab(self):
        """Setup the Utilities tab without scroll functionality"""
        # Create a main frame for the utilities tab 
        main_frame = ttk.Frame(self.utilities_tab, padding="5")
        main_frame.pack(expand=True, fill="both")
        main_frame.pack_propagate(False)  

        #------------------------------------------------------------------
        # CUP Converter Section
        cup_frame = ttk.LabelFrame(main_frame, text="CUP File Converter", padding="5")
        cup_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20)  # Use boolean True, not a string

        # Input file selection
        ttk.Label(cup_frame, text="Input CUP file:").grid(row=1, column=0, sticky="w")
        self.cup_input_path = tk.StringVar()
        ttk.Entry(cup_frame, textvariable=self.cup_input_path).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(cup_frame, text="Browse", command=lambda: self.browse_file("CUP File", self.cup_input_path, [("CUP files", "*.cup")])).grid(row=1, column=2)
        
        # Output file selection
        ttk.Label(cup_frame, text="Output CSV file:").grid(row=2, column=0, sticky="w", pady=5)
        self.cup_output_path = tk.StringVar()
        ttk.Entry(cup_frame, textvariable=self.cup_output_path).grid(row=2, column=1, sticky="ew", padx=5)
        ttk.Button(cup_frame, text="Browse", command=lambda: self.browse_save_file("CSV File", self.cup_output_path, [("CSV files", "*.csv")])).grid(row=2, column=2)
        
        # Convert button
        ttk.Button(cup_frame, text="Convert CUP to CSV", command=self.convert_cup_file).grid(row=3, column=1, pady=10)

        cup_frame.grid_columnconfigure(1, weight=1)
        
        #-------------------------------------------------------------

        # Process Passes Section
        process_passes_frame = ttk.LabelFrame(main_frame, text="Process Mountain Passes", padding="5")
        process_passes_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20) 
        
        # Parent folder selection
        ttk.Label(process_passes_frame, text="Parent folder:").grid(row=0, column=0, sticky="w", pady=5)
        self.process_passes_root_path = tk.StringVar()
        ttk.Entry(process_passes_frame, textvariable=self.process_passes_root_path).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(process_passes_frame, text="Browse", command=lambda: self.browse_directory("Parent Folder", self.process_passes_root_path)).grid(row=0, column=2)
        
        # Mountain passes reference geojson
        ttk.Label(process_passes_frame, text="Reference Passes:").grid(row=1, column=0, sticky="w", pady=5)
        self.ref_mountain_passes_path = tk.StringVar(
            value=resource_path(os.path.join("data", "passes", "passesosmalps.geojson"))
        )
        ttk.Entry(process_passes_frame, textvariable=self.ref_mountain_passes_path).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(process_passes_frame, text="Browse", command=lambda: self.browse_file("Reference Passes", self.ref_mountain_passes_path, [("GeoJSON", "*.geojson")])).grid(row=1, column=2)
        
        # Help section
        self.help_visible = False
        help_button = ttk.Button(process_passes_frame, text="Show Help ▼", command=lambda: self.toggle_help_section(help_button, help_frame))
        help_button.grid(row=2, column=1,  pady=(10, 0), sticky='ew')
        
        # Help content frame (initially hidden)
        help_frame = ttk.Frame(process_passes_frame)
        help_frame.grid(row=3, column=0, columnspan=3, sticky='ew', padx=5)
        help_frame.grid_remove()  # Initially hidden
        
        help_text = """This tool processes mountain passes data in three steps:
        
1. Collection: Gathers and merges all CSV files containing pass data from the parent folder and all subfolders.
2. Conversion: Converts the collected data and transforms it to the correct coordinate system.
3. Filtering: Compares with known passes from Open Street Map database and keeps only the closest matches.

Output will be saved in:
parent_folder/processed_passes/processed_passes.geojson"""
        
        help_label = ttk.Label(help_frame, text=help_text, justify='left', wraplength=450)
        help_label.pack(pady=10)
        
        # Process button
        ttk.Button(process_passes_frame, text="Process Passes", command=self.process_passes).grid(row=4, column=0, columnspan=3, pady=10)

        process_passes_frame.grid_columnconfigure(1, weight=1)

        main_frame.grid_columnconfigure(0,weight=1)





    def browse_file(self, file_type, var, filetypes=None, initialdir=None):
        """Browse for a file and update the corresponding variable"""
        # Set default initial directories based on file type
        if initialdir is None:
            if file_type == "Airfield File":
                initialdir = resource_path(os.path.join("data", "airfields"))
            elif file_type == "Topography File":
                initialdir = resource_path(os.path.join("data", "topography"))
            elif file_type == "Reference Passes":
                initialdir = resource_path(os.path.join("data", "passes"))
            else:
                initialdir = "."
        
        # Create directory if it doesn't exist
        os.makedirs(initialdir, exist_ok=True)
        
        # Default filetypes if none provided
        if filetypes is None:
            filetypes = [("All files", "*.*")]
        
        path = filedialog.askopenfilename(
            title=f"Select {file_type}",
            initialdir=initialdir,
            filetypes=filetypes
        )
        if path:
            var.set(path)

    def browse_save_file(self, file_type, var, filetypes=None, initialdir=None):
        """Browse for a save location and update the corresponding variable"""
        if filetypes is None:
            filetypes = [("All files", "*.*")]
            
        path = filedialog.asksaveasfilename(
            title=f"Save {file_type}",
            filetypes=filetypes,
            defaultextension=filetypes[0][1].split('.')[-1],
            initialdir=initialdir
        )
        if path:
            var.set(path)
            
    def convert_cup_file(self):
        """Convert CUP file to CSV using cupConvert.py logic"""
        input_path = resource_path(self.cup_input_path.get())
        output_path = resource_path(self.cup_output_path.get())
        
        if not input_path or not output_path:
            messagebox.showerror("Error", "Please select both input and output files.")
            return
            
        try:
            # Read the input CUP file
            df = pd.read_csv(input_path)
            
            # Remove the version line if it's at the beginning
            df = df[df['name'] != 'version=']
            
            # Convert coordinates
            df['lat_dd'] = df['lat'].apply(convert_coord)
            df['lon_dd'] = df['lon'].apply(convert_coord)
            
            # Select and rename fields
            df = df[['name', 'lon_dd', 'lat_dd']]
            df.rename(columns={'lat_dd': 'y', 'lon_dd': 'x'}, inplace=True)
            
            # Save to CSV
            df.to_csv(output_path, index=False)
            
            messagebox.showinfo("Success", "File converted successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to convert file: {str(e)}")

    def refresh_yaml_list(self):
        """Refresh the list of YAML files in the dropdown"""
        self.yaml_files = [f for f in os.listdir('.') if f.endswith('.yaml')]
        self.config_dropdown['values'] = self.yaml_files

    def load_selected_config(self, event=None):
        """Load the selected configuration file"""
        selected = self.config_dropdown.get()
        if not selected:
            return
            
        try:
            with open(selected, 'r') as f:
                config = yaml.safe_load(f)
                
            # Update GUI fields with loaded values
            self.name.set(config.get('name', 'gui_generated'))
            self.airfield_path.set(resource_path(config['input_files']['airfield_file']))
            self.topo_path.set(resource_path(config['input_files']['topography_file']))
            self.result_path.set(resource_path(config['input_files']['result_folder']))
            
            self.glide_ratio.set(str(config['glide_parameters']['glide_ratio']))
            self.ground_clearance.set(str(config['glide_parameters']['ground_clearance']))
            self.circuit_height.set(str(config['glide_parameters']['circuit_height']))
            
            self.max_altitude.set(str(config['calculation_parameters']['max_altitude']))
            
            self.gurumaps.set(config.get('gurumaps', True))
            self.export_passes.set(config.get('exportPasses', False))
            self.reset_results.set(config.get('reset_results', True))
            self.clean_temporary_files.set(config.get('clean_temporary_files', True))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

    def save_config(self):
        """Save current parameters to a YAML configuration file"""
        try:
            self.validate_inputs()
            config = self.create_config_dict()
            
            # Create filename from config name
            filename = resource_path(f"{self.name.get().strip()}.yaml")
            
            # Check if file exists
            if os.path.exists(filename):
                if not messagebox.askyesno("Confirm Overwrite", 
                    f"File '{filename}' already exists. Do you want to overwrite it?"):
                    return
            
            with open(filename, 'w') as f:
                # Custom formatting function to match the desired style
                def custom_str_presenter(dumper, data):
                    if len(data.splitlines()) > 1:  # check for multiline string
                        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
                    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
                
                # Add custom string presenter to the YAML dumper
                yaml.add_representer(str, custom_str_presenter)
                
                # Write the header
                f.write(f"name: {config['name']}\n\n")
                
                # Write input_files section
                f.write("input_files:\n")
                for key, value in config['input_files'].items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
                
                # Write CRS section
                f.write("CRS:\n")
                f.write(f"  name: {config['CRS']['name']}\n")
                f.write(f"  definition: {config['CRS']['definition']}\n")
                f.write("\n")
                
                # Write glide_parameters section
                f.write("glide_parameters:\n")
                for key, value in config['glide_parameters'].items():
                    # Convert float to int by removing decimal point
                    f.write(f"  {key}: {int(value)}\n")
                f.write("\n")
                
                # Write calculation_parameters section
                f.write("calculation_parameters:\n")
                f.write(f"  max_altitude: {int(config['calculation_parameters']['max_altitude'])}\n")
                f.write("\n")
                
                # Write rendering section
                f.write("rendering:\n")
                f.write(f"  contour_height: {int(config['rendering']['contour_height'])}\n")
                f.write("\n")
                
                # Write boolean parameters
                f.write(f"gurumaps: {str(config['gurumaps']).lower()}\n")
                f.write(f"exportPasses: {str(config['exportPasses']).lower()}\n")
                f.write(f"reset_results: {str(config['reset_results']).lower()}\n")
                f.write(f"clean_temporary_files: {str(config['clean_temporary_files']).lower()}\n")
                f.write("\n")
                
                # Write merged_output_name
                f.write(f"merged_output_name: {config['merged_output_name']}\n")
            
            # Refresh the dropdown list after saving
            self.refresh_yaml_list()
            messagebox.showinfo("Success", "Configuration saved successfully!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def create_config_dict(self):
        """Create a configuration dictionary from GUI inputs with ordered keys matching full.yaml"""
        from collections import OrderedDict
        
        config = OrderedDict([
            ("name", self.name.get() + " "),  # Add space to match format
            
            ("input_files", OrderedDict([
                ("airfield_file", self.airfield_path.get()),
                ("topography_file", self.topo_path.get()),
                ("result_folder", self.result_path.get()),
                ("compute", resource_path(os.path.join(".", "compute.exe"))),
                ("mapcssTemplate", resource_path(os.path.join(".", "templates", "mapcss.mapcss")))
            ])),
            
            ("CRS", OrderedDict([
                ("name", "100001"),
                ("definition", "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs")
            ])),
            
            ("glide_parameters", OrderedDict([
                ("glide_ratio", float(self.glide_ratio.get())),
                ("ground_clearance", float(self.ground_clearance.get())),
                ("circuit_height", float(self.circuit_height.get()))
            ])),
            
            ("calculation_parameters", OrderedDict([
                ("max_altitude", float(self.max_altitude.get()))
            ])),
            
            ("rendering", OrderedDict([
                ("contour_height", 100)
            ])),
            
            ("gurumaps", self.gurumaps.get()),
            ("exportPasses", self.export_passes.get()),
            ("reset_results", self.reset_results.get()),
            ("clean_temporary_files", self.clean_temporary_files.get()),
            
            ("merged_output_name", "merged_output")
        ])
        
        return config
    
    def validate_inputs(self):
        """Validate all input fields"""
        if not self.airfield_path.get():
            raise ValueError("Airfield file path is required")
        if not self.topo_path.get():
            raise ValueError("Topography file path is required")
        if not self.result_path.get():
            raise ValueError("Result folder path is required")
        
        # Validate numeric inputs
        try:
            float(self.glide_ratio.get())
            float(self.ground_clearance.get())
            float(self.circuit_height.get())
            float(self.max_altitude.get())
        except ValueError:
            raise ValueError("All numeric parameters must be valid numbers")
    
    def run_processing(self):
        """Run the main processing with current parameters"""
        try:
            self.validate_inputs()
            config = self.create_config_dict()
            
            # Create temporary config file
            temp_config_path = resource_path(os.path.join(self.result_path.get(), "temp_config.yaml"))
            
            with open(temp_config_path, 'w') as f:
                # Write the config in the same format as save_config
                f.write(f"name: {config['name']}\n\n")
                
                f.write("input_files:\n")
                for key, value in config['input_files'].items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
                
                f.write("CRS:\n")
                f.write(f"  name: {config['CRS']['name']}\n")
                f.write(f"  definition: {config['CRS']['definition']}\n")
                f.write("\n")
                
                f.write("glide_parameters:\n")
                for key, value in config['glide_parameters'].items():
                    f.write(f"  {key}: {int(value)}\n")
                f.write("\n")
                
                f.write("calculation_parameters:\n")
                f.write(f"  max_altitude: {int(config['calculation_parameters']['max_altitude'])}\n")
                f.write("\n")
                
                f.write("rendering:\n")
                f.write(f"  contour_height: {int(config['rendering']['contour_height'])}\n")
                f.write("\n")
                
                f.write(f"gurumaps: {str(config['gurumaps']).lower()}\n")
                f.write(f"exportPasses: {str(config['exportPasses']).lower()}\n")
                f.write(f"reset_results: {str(config['reset_results']).lower()}\n")
                f.write(f"clean_temporary_files: {str(config['clean_temporary_files']).lower()}\n")
                f.write("\n")
                
                f.write(f"merged_output_name: {config['merged_output_name']}\n")
            
            # Disable the run button while processing
            self.run_button.state(['disabled'])
            
            # Start processing in a separate thread
            thread = threading.Thread(target=lambda: self.process_data(temp_config_path))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def process_data(self, config_path):
        """Run the main processing function"""
        try:
            multiprocessing.freeze_support()
            launch.main(resource_path(config_path))
            self.root.after(0, self.processing_complete)
        except Exception as e:
            error_message = str(e)  # Capture the error message
            self.root.after(0, lambda: self.processing_error(error_message))  # Pass it to the lambda
        finally:
            # Clean up temporary config file
            if os.path.exists(config_path):
                os.remove(config_path)
    
    def processing_complete(self):
        """Called when processing is complete"""
        self.run_button.state(['!disabled'])
        messagebox.showinfo("Success", "Processing completed successfully!")
    
    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.run_button.state(['!disabled'])
        messagebox.showerror("Error", f"An error occurred during processing:\n{error_message}")
    
    def clear_log(self):
        """Clear the status text widget"""
        self.status_text.delete(1.0, tk.END)
    
    def open_results_folder(self):
        """Open the results folder in the system's file explorer"""
        result_path = resource_path(self.result_path.get())
        if not result_path:
            messagebox.showwarning("Warning", "Please select a result folder first.")
            return
            
        if not os.path.exists(result_path):
            messagebox.showwarning("Warning", "Results folder does not exist yet.")
            return
            
        # Open folder in the default file explorer
        if sys.platform == 'darwin':  # macOS
            subprocess.run(['open', result_path])
        elif sys.platform == 'win32':  # Windows
            os.startfile(result_path)
        else:  # Linux
            subprocess.run(['xdg-open', result_path])
    
    def open_airfield_file(self):
        """Open the airfield file with system's default application or let user choose"""
        file_path = resource_path(self.airfield_path.get())
        
        if not file_path:
            messagebox.showwarning("Warning", "Please select an airfield file first.")
            return
            
        if not os.path.exists(file_path):
            messagebox.showwarning("Warning", "Selected file does not exist.")
            return
            
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', '-a', 'TextEdit', file_path])  # You can change TextEdit to your preferred editor
            elif sys.platform == 'win32':  # Windows
                os.startfile(file_path)  # This will open with the default application
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")
    
    def browse_directory(self, dir_type, var):
        """Browse for a directory and update the corresponding variable"""
        # Set default initial directory based on directory type
        if dir_type == "Results Folder" or dir_type == "Parent Folder":
            initialdir = resource_path(os.path.join(".", "results"))
        else:
            initialdir = "."
        
        # Create directory if it doesn't exist
        os.makedirs(initialdir, exist_ok=True)
        
        path = filedialog.askdirectory(
            title=f"Select {dir_type}",
            initialdir=initialdir
        )
        if path:
            var.set(path)
            
    def process_passes(self):
        """Process mountain passes using process_passes.py logic"""
        root_folder = resource_path(self.process_passes_root_path.get())
        mountain_passes_path = resource_path(self.ref_mountain_passes_path.get())
        
        if not all([root_folder, mountain_passes_path]):
            messagebox.showerror("Error", "Please select all required paths.")
            return
        
        try:
            from utils.process_passes import process_passes
            # Custom CRS for the Alps region
            input_crs = "+proj=lcc +lat_0=45.7 +lon_0=10.5 +lat_1=44 +lat_2=47.4 +x_0=700000 +y_0=250000 +datum=WGS84 +units=m +no_defs"
            
            # Create output directory in the parent folder
            output_dir = resource_path(os.path.join(root_folder, "processed_passes"))
            os.makedirs(output_dir, exist_ok=True)
            
            # Set paths for intermediate and output files
            intermediate_path = resource_path(os.path.join(output_dir, "intermediate_passes.geojson"))
            output_path = resource_path(os.path.join(output_dir, "processed_passes.geojson"))
            
            process_passes(root_folder, input_crs, intermediate_path, mountain_passes_path, output_path)
            messagebox.showinfo("Success", "Passes processed successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process passes: {str(e)}")
    
    def toggle_help_section(self, button, help_frame):
        """Toggle the visibility of the help section"""
        self.help_visible = not self.help_visible
        if self.help_visible:
            help_frame.grid()
            button.configure(text="Hide Help ▲")
        else:
            help_frame.grid_remove()
            button.configure(text="Show Help ▼")
    
    def open_download_page(self):
        """Opens the system's default browser to the download page."""
        webbrowser.open("https://drive.google.com/drive/folders/1MeU_GSd5152h_8e1rB8i-fspA9_dqah-?usp=sharing")  # Replace with the actual URL you want to open.
    
    # def _on_run_canvas_configure(self, event):
    #     """Center the scrollable frame horizontally and adjust its width to the available canvas width."""
    #     available_width = event.width
    #     # Adjust the width of the scrollable frame to fully occupy the canvas
    #     self.canvas.itemconfigure(self.canvas_window, width=available_width)
    #     # Center the scrollable frame horizontally in the canvas
    #     self.canvas.coords(self.canvas_window, available_width / 2, 0)

    class TextRedirector:
        """Redirect stdout to the text widget"""
        def __init__(self, widget):
            self.widget = widget
        
        def write(self, str):
            self.widget.insert(tk.END, str)
            self.widget.see(tk.END)
        
        def flush(self):
            pass

def main():
    root = tk.Tk()
    app = MountainCirclesGUI(root)
    root.mainloop()

if __name__ == "__main__":
    print('gui.py\n')
    print(sys.path)
    main()