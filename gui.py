import os
import sys
import subprocess
import threading
import multiprocessing
import webbrowser
import platform

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd
import yaml

from config import load_settings, save_settings
from utils.cupConvert import convert_coord
import launch


class MountainCirclesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mountain Circles")
        self.root.resizable(True, True)
        self.root.geometry("1200x1200")

        # Variable to store the user's personal data folder
        self.main_folder = tk.StringVar(value="")
        self.calc_script = tk.StringVar(value="")
        print("-------welcome here---------")

        # Load stored settings if they exist

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

        # Initialize variables with empty values
        self.config_folder = tk.StringVar(value="")
        self.GMstyles_folder = tk.StringVar(value="")
        self.name = tk.StringVar(value="")
        self.airfield_path = tk.StringVar(value="")
        self.topo_path = tk.StringVar(value="")
        self.topo_CRSfile = tk.StringVar(value="")
        self.input_crs = tk.StringVar(value="")
        self.result_path = tk.StringVar(value="")
        self.real_result_path = tk.StringVar(value="")
        self.glide_ratio = tk.StringVar(value="")
        self.ground_clearance = tk.StringVar(value="")
        self.circuit_height = tk.StringVar(value="")
        self.max_altitude = tk.StringVar(value="")
        self.contour_height = tk.StringVar(value="")
        self.gurumaps = tk.BooleanVar(value=False)
        self.export_passes = tk.BooleanVar(value=False)
        self.reset_results = tk.BooleanVar(value=False)
        self.clean_temporary_files = tk.BooleanVar(value=False)
        self.ref_mountain_passes_path = tk.StringVar(value="")
        self.cup_input_path = tk.StringVar(value="")
        self.cup_output_path = tk.StringVar(value="")
        self.process_passes_CRSfile = tk.StringVar(value="")
        self.merged_output_name = tk.StringVar(value="aa")
        # Setup tabs
        self.setup_download_tab()
        self.setup_run_tab()
        self.setup_utilities_tab()
        self.load_settings()



        # Bind window close to saving settings
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_download_tab(self):
        """Setup the Download tab without scroll functionality"""
        # Create a main frame for the download tab that fills the tab entirely
        main_frame = ttk.Frame(self.download_tab)
        main_frame.pack(expand=True, fill="both")

        # Create a content frame and center it within the main frame
        content_frame = ttk.Frame(main_frame)
        content_frame.place(relx=0.5, rely=0.5, anchor='center')

        # Add label with the text
        label = ttk.Label(
            content_frame, text="Download data files and directory structure to start your project...")
        label.pack(pady=10)

        # Add the download button which opens the system browser to a web address
        button = ttk.Button(content_frame, text="Download Now",
                            command=self.open_download_page)
        button.pack(pady=10)

        label = ttk.Label(
            content_frame, text="... unzip the file, check the contents, and put the MountainCircles folder where you like")
        label.pack(pady=5)

        label = ttk.Label(
            content_frame, text="( DO NOT RENAME THE FOLDERS AND FILES )")
        label.pack(pady=5)

        label = ttk.Label(
            content_frame, text="and tell the app where you put :")
        label.pack(pady=5)

        param_frame = ttk.Frame(content_frame, padding="5")
        param_frame.pack(pady=10)

        # MountainCircles Folder
        ttk.Label(param_frame, text="the MountainCircle folder:").grid(
            row=1, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.main_folder).grid(
            row=1, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_directory(
            "MountainCircles Folder", self.main_folder)).grid(row=1, column=2)

        # Calculation script
        ttk.Label(param_frame, text="the calculation script:").grid(
            row=3, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.calc_script).grid(
            row=3, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_file(
            "Calculation script", self.calc_script)).grid(row=3, column=2)

        param_frame.grid_columnconfigure(1, weight="1")

    def setup_run_tab(self):
        """Setup the Run tab with a simple layout using only frames."""
        # Create a main frame that fills the Run tab
        main_frame = ttk.Frame(self.run_tab, padding="5")
        main_frame.pack(expand=True, fill="both")
        main_frame.pack_propagate(False)

        # ------------------------------------------------------------

        # Create configuration frame at the top
        config_frame = ttk.LabelFrame(main_frame, padding="5")
        # config_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        config_frame.grid(row=0, column=0, columnspan=3,
                          sticky=(tk.W, tk.E), pady=5)

        # Get list of YAML files and set up the config dropdown
        self.yaml_files = []

        # Add Config dropdown and refresh button
        ttk.Label(config_frame, text="Select Config:").grid(
            row=0, column=0, padx=5, sticky="ew")
        self.config_dropdown = ttk.Combobox(
            config_frame, values=self.yaml_files, width=30)
        self.config_dropdown.grid(row=0, column=1, padx=5, sticky="ew")
        self.config_dropdown.bind(
            '<<ComboboxSelected>>', self.load_selected_config)

        # Set default selection to the first available value if any exist
        if self.yaml_files:
            self.config_dropdown.current(0)
            self.load_selected_config(self)

        ttk.Button(config_frame, text="Refresh List", command=self.refresh_yaml_list).grid(
            row=0, column=2, padx=5, sticky="ew")

        # Configure grid columns to spread evenly
        config_frame.grid_columnconfigure(0, weight=0)
        config_frame.grid_columnconfigure(1, weight=2)
        config_frame.grid_columnconfigure(2, weight=0)

        # -------------------------------------------------------------

        # Create parameter input frame
        param_frame = ttk.LabelFrame(
            main_frame, text="Config Parameters :", padding="5")
        param_frame.grid(row=1, column=0, columnspan=3,
                         sticky=(tk.W, tk.E), pady=5)

        # Config name and Save button
        ttk.Label(param_frame, text="Config name:").grid(
            row=1, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.name).grid(
            row=1, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Save Config",
                   command=self.save_config).grid(row=1, column=2)

        # Airfield file selection
        ttk.Label(param_frame, text="Airfield File:").grid(
            row=2, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.airfield_path).grid(
            row=2, column=1, padx=5, sticky="ew")
        airfield_buttons_frame = ttk.Frame(param_frame)
        airfield_buttons_frame.grid(row=2, column=2, sticky="w")
        ttk.Button(airfield_buttons_frame, text="Browse", command=lambda: self.browse_file(
            "Airfield File", self.airfield_path)).grid(row=0, column=0, padx=2)
        ttk.Button(airfield_buttons_frame, text="Open/edit",
                   command=self.open_airfield_file).grid(row=0, column=1, padx=2)

        # Topography file selection
        ttk.Label(param_frame, text="Topography File:").grid(
            row=3, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.topo_path).grid(
            row=3, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_file(
            "Topography File", self.topo_path)).grid(row=3, column=2)

        # CRS file selection added after topography section
        ttk.Label(param_frame, text="CRS File:").grid(
            row=4, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.topo_CRSfile).grid(
            row=4, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_file(
            "CRS File", self.topo_CRSfile, [("Text files", "*.txt")])).grid(row=4, column=2)

        # Result folder selection (shifted down to row 5)
        ttk.Label(param_frame, text="Result Folder: (.../RESULTS/configName)").grid(
            row=5, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.result_path).grid(
            row=5, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_directory(
            "Results Folder", self.result_path)).grid(row=5, column=2)

        # Glide Parameters Section
        ttk.Label(param_frame, text="Glide Parameters", font=(
            'Arial', 10, 'bold')).grid(row=6, column=0, sticky="w", pady=(15, 5))

        # Glide ratio
        ttk.Label(param_frame, text="Glide Ratio:").grid(
            row=7, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.glide_ratio,
                  width=10).grid(row=7, column=1, sticky="w", padx=5)

        # Ground clearance
        ttk.Label(param_frame, text="Ground Clearance (m):").grid(
            row=8, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.ground_clearance,
                  width=10).grid(row=8, column=1, sticky="w", padx=5)

        # Circuit height
        ttk.Label(param_frame, text="Circuit Height (m):").grid(
            row=9, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.circuit_height,
                  width=10).grid(row=9, column=1, sticky="w", padx=5)

        # Max altitude
        ttk.Label(param_frame, text="Max Altitude (m):").grid(
            row=10, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.max_altitude,
                  width=10).grid(row=10, column=1, sticky="w", padx=5)

        # Additional Options Section
        ttk.Label(param_frame, text="Additional Options", font=(
            'Arial', 10, 'bold')).grid(row=11, column=0, sticky="w", pady=(15, 5))

        # New Field: Contour Height
        ttk.Label(param_frame, text="Altitude delta between circles (m):").grid(
            row=12, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.contour_height,
                  width=10).grid(row=12, column=1, sticky="w", padx=5)

        # Checkboxes
        ttk.Checkbutton(param_frame, text="Wipe result folder (when testing)",
                        variable=self.reset_results).grid(row=13, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Generate data files for Guru Maps",
                        variable=self.gurumaps).grid(row=14, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Create mountain passes files",
                        variable=self.export_passes).grid(row=15, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Clean temporary files",
                        variable=self.clean_temporary_files).grid(row=16, column=0, sticky="w")

        param_frame.grid_columnconfigure(1, weight="1")

        # Control buttons frame
        control_btn_frame = ttk.Frame(main_frame)
        control_btn_frame.grid(row=17, column=0, columnspan=3, pady=10)
        ttk.Button(control_btn_frame, text="Clear Log",
                   command=self.clear_log).pack(side=tk.LEFT, padx=5)

        self.run_button = ttk.Button(
            control_btn_frame, text="Run Processing", command=self.run_processing)
        self.run_button.pack(side=tk.LEFT, padx=5)

        self.open_results_button = ttk.Button(
            control_btn_frame, text="Open Results Folder", command=self.open_results_folder)
        self.open_results_button.pack(side=tk.LEFT, padx=5)

        # Status display area
        ttk.Label(main_frame, text="Status:", font=('Arial', 10, 'bold')).grid(
            row=18, column=0, sticky="w", pady=5)
        self.status_text = tk.Text(main_frame)
        self.status_text.grid(
            row=19, column=0, columnspan=3, pady=5, sticky="nsew")
        scroller = ttk.Scrollbar(
            main_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        scroller.grid(row=19, column=3, sticky="ns")
        self.status_text['yscrollcommand'] = scroller.set

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(19, weight=1)

    def setup_utilities_tab(self):
        """Setup the Utilities tab without scroll functionality"""
        # Create a main frame for the utilities tab
        main_frame = ttk.Frame(self.utilities_tab, padding="5")
        main_frame.pack(expand=True, fill="both")
        main_frame.pack_propagate(False)

        # ------------------------------------------------------------------
        # CUP Converter Section
        cup_frame = ttk.LabelFrame(
            main_frame, text="CUP File Converter", padding="5")
        cup_frame.grid(row=0, column=0, columnspan=3, sticky=(
            tk.W, tk.E), pady=20)  # Use boolean True, not a string

        # Input file selection
        ttk.Label(cup_frame, text="Input CUP file:").grid(
            row=1, column=0, sticky="w")
        ttk.Entry(cup_frame, textvariable=self.cup_input_path).grid(
            row=1, column=1, sticky="ew", padx=5)
        ttk.Button(cup_frame, text="Browse", command=lambda: self.browse_file(
            "CUP File", self.cup_input_path, [("CUP files", "*.cup")])).grid(row=1, column=2)

        # Output file selection
        ttk.Label(cup_frame, text="Output CSV file:").grid(
            row=2, column=0, sticky="w", pady=5)
        ttk.Entry(cup_frame, textvariable=self.cup_output_path).grid(
            row=2, column=1, sticky="ew", padx=5)
        ttk.Button(cup_frame, text="Browse", command=lambda: self.browse_save_file(
            "CSV File", self.cup_output_path, [("CSV files", "*.csv")])).grid(row=2, column=2)

        # Convert button
        ttk.Button(cup_frame, text="Convert CUP to CSV",
                   command=self.convert_cup_file).grid(row=3, column=1, pady=10)

        cup_frame.grid_columnconfigure(1, weight=1)

        # -------------------------------------------------------------

        # Process Passes Section
        process_passes_frame = ttk.LabelFrame(
            main_frame, text="Process Mountain Passes", padding="5")
        process_passes_frame.grid(
            row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20)

        # Parent folder selection
        ttk.Label(process_passes_frame, text="Parent folder:").grid(
            row=0, column=0, sticky="w", pady=5)
        self.process_passes_root_path = tk.StringVar()
        ttk.Entry(process_passes_frame, textvariable=self.process_passes_root_path).grid(
            row=0, column=1, sticky="ew", padx=5)
        ttk.Button(process_passes_frame, text="Browse", command=lambda: self.browse_directory(
            "Parent Folder", self.process_passes_root_path)).grid(row=0, column=2)

        # Mountain passes reference geojson
        ttk.Label(process_passes_frame, text="Reference Passes:").grid(
            row=1, column=0, sticky="w", pady=5)
        ttk.Entry(process_passes_frame, textvariable=self.ref_mountain_passes_path).grid(
            row=1, column=1, sticky="ew", padx=5)
        ttk.Button(process_passes_frame, text="Browse", command=lambda: self.browse_file(
            "Reference Passes", self.ref_mountain_passes_path, [("GeoJSON", "*.geojson")])).grid(row=1, column=2)

        # CRS File
        ttk.Label(process_passes_frame, text="CRS File:").grid(
            row=2, column=0, sticky="w", pady=5)
        ttk.Entry(process_passes_frame, textvariable=self.process_passes_CRSfile).grid(
            row=2, column=1, sticky="ew", padx=5)
        ttk.Button(process_passes_frame, text="Browse", command=lambda: self.browse_file(
            "CRS File", self.process_passes_CRSfile, [("Text files", "*.txt")])).grid(row=2, column=2)

        # Help section
        self.help_visible = False
        help_button = ttk.Button(process_passes_frame, text="Show Help ▼",
                                 command=lambda: self.toggle_help_section(help_button, help_frame))
        help_button.grid(row=3, column=1, pady=(10, 0), sticky='ew')

        # Help content frame (initially hidden)
        help_frame = ttk.Frame(process_passes_frame)
        help_frame.grid(row=4, column=0, columnspan=3, sticky='ew', padx=5)
        help_frame.grid_remove()  # Initially hidden

        help_text = """This tool processes mountain passes data in three steps:
        
1. Collection: Gathers and merges all CSV files containing pass data from the parent folder and all subfolders.
2. Conversion: Converts the collected data and transforms it to the correct coordinate system.
3. Filtering: Compares with known passes from Open Street Map database and keeps only the closest matches.

Output will be saved in:
parent_folder/processed_passes/processed_passes.geojson"""

        help_label = ttk.Label(help_frame, text=help_text,
                               justify='left', wraplength=450)
        help_label.pack(pady=10)

        # Process button
        ttk.Button(process_passes_frame, text="Process Passes", command=self.process_passes).grid(
            row=5, column=0, columnspan=3, pady=10)

        process_passes_frame.grid_columnconfigure(1, weight=1)

        main_frame.grid_columnconfigure(0, weight=1)

    def open_download_page(self):
        """Opens the system's default browser to the download page."""
        webbrowser.open(
            # Replace with the actual URL you want to open.
            "https://drive.google.com/drive/folders/1MeU_GSd5152h_8e1rB8i-fspA9_dqah-?usp=sharing")

    def browse_file(self, file_type, var, filetypes=None, initialdir=None):
        """Browse for a file and update the corresponding variable"""
        if initialdir is None:
            initialdir = self.main_folder.get()
        if var == self.calc_script:
            if os.path.exists(os.path.normpath(os.path.join(self.main_folder.get(), "common files", "calculation script"))):
                initialdir = os.path.normpath(os.path.join(initialdir, "common files", "calculation script"))

        if filetypes is None:
            filetypes = [("All files", "*.*")]

        path = filedialog.askopenfilename(
            title=f"Select {file_type}",
            initialdir=initialdir,
            filetypes=filetypes
        )
        if path:
            var.set(path)
            # If browsing for a Topography File, check if there is a .txt file in the same folder.
            if file_type == "Topography File":
                directory = os.path.dirname(path)
                try:
                    # List all .txt files in the directory (using sorted order to be predictable)
                    txt_files = sorted([f for f in os.listdir(
                        directory) if f.lower().endswith('.txt')])
                    if txt_files:
                        # Assign the first .txt file to self.topo_CRSfile
                        self.topo_CRSfile.set(os.path.normpath(os.path.join(directory, txt_files[0])))
                        print(
                            f"Automatically detected CRS file: {self.topo_CRSfile.get()}")
                except Exception as e:
                    print(f"Error checking for CRS file in {directory}: {e}")

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

    def browse_directory(self, dir_type, var):
        """Browse for a directory and update the corresponding variable"""
        # Use self.main_folder as the initial directory if it is set; otherwise, use the current working directory.
        initial_dir = self.main_folder.get() if self.main_folder.get() else os.getcwd()
        path = filedialog.askdirectory(
            title=f"Select {dir_type}", initialdir=initial_dir)
        if path:
            var.set(path)
            if dir_type == "Results Folder":
                self.real_result_path.set(os.path.normpath(os.path.join(path, self.name.get())))
            if dir_type == "MountainCircles Folder":
                self.config_folder.set(os.path.normpath(os.path.join(path, "common files", "configuration files")))
                self.GMstyles_folder.set(os.path.normpath(os.path.join(path, "common files", "Guru Map styles")))
                self.refresh_yaml_list()
                # Retrieve system name and architecture using the platform module
                os_name = platform.system()
                architecture = platform.machine()
                print(f"Operating System: {os_name}")
                print(f"Architecture: {architecture}")
                # For macOS ARM64
                if os_name == "Darwin" and architecture in ["arm64", "aarch64"]:
                    calc_path = os.path.normpath(os.path.join(path, "common files", "calculation script", "compute_mac_arm"))
                    print(calc_path)
                    if os.path.exists(calc_path):  # Optionally check if the path exists
                        self.calc_script.set(calc_path)
                # For macOS x86_64
                if os_name == "Darwin" and architecture in ["AMD64", "x86_64"]:
                    calc_path = os.path.normpath(os.path.join(path, "common files", "calculation script", "compute_mac_x86_64"))
                    if os.path.exists(calc_path):
                        self.calc_script.set(calc_path)
                # For Windows ARM64
                if os_name == "Windows" and architecture in ["arm64", "aarch64"]:
                    calc_path = os.path.normpath(os.path.join(path, "common files", "calculation script", "compute_windows_arm64.exe"))
                    if os.path.exists(calc_path):
                        self.calc_script.set(calc_path)
                # For Windows x86_64
                if os_name == "Windows" and architecture in ["AMD64", "x86_64"]:
                    calc_path = os.path.normpath(os.path.join(path, "common files", "calculation script", "compute_windows_amd64.exe"))
                    if os.path.exists(calc_path):
                        self.calc_script.set(calc_path)
                print(self.calc_script.get())

    def open_airfield_file(self):
        """Open the airfield file with system's default application or let user choose"""
        file_path = self.airfield_path.get()

        if not file_path:
            messagebox.showwarning(
                "Warning", "Please select an airfield file first.")
            return

        if not os.path.exists(file_path):
            messagebox.showwarning("Warning", "Selected file does not exist.")
            return

        try:
            if sys.platform == 'darwin':  # macOS
                # You can change TextEdit to your preferred editor
                subprocess.run(['open', '-a', 'TextEdit', file_path])
            elif sys.platform == 'win32':  # Windows
                # This will open with the default application
                os.startfile(file_path)
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def refresh_yaml_list(self, active_config=None):
        """Refresh the list of YAML files in the dropdown.
        
        If active_config is provided and exists in the list,
        that config file will be automatically selected and loaded.
        """
        directory = self.config_folder.get()
        if os.path.isdir(directory):
            self.yaml_files = [f for f in os.listdir(directory) if f.endswith('.yaml')]
        else:
            self.yaml_files = []
        self.config_dropdown['values'] = self.yaml_files

        if self.yaml_files:
            if active_config and active_config in self.yaml_files:
                self.config_dropdown.current(self.yaml_files.index(active_config))
            else:
                self.config_dropdown.current(0)
            self.load_selected_config()

    def load_selected_config(self, event=None):
        """Load the selected configuration file"""
        selected = self.config_dropdown.get()
        if not selected:
            return

        # Construct the full path to the selected YAML file
        full_path = os.path.normpath(os.path.join(self.config_folder.get(), selected))

        try:
            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            # Update GUI fields with loaded values
            self.name.set(config.get('name', 'gui_generated'))
            self.airfield_path.set(config['input_files']['airfield_file'])
            self.topo_path.set(config['input_files']['topography_file'])
            self.topo_CRSfile.set(config['input_files']['CRS_file'])
            self.result_path.set(config['input_files']['result_folder'])

            self.glide_ratio.set(
                str(config['glide_parameters']['glide_ratio']))
            self.ground_clearance.set(
                str(config['glide_parameters']['ground_clearance']))
            self.circuit_height.set(
                str(config['glide_parameters']['circuit_height']))

            self.max_altitude.set(
                str(config['calculation_parameters']['max_altitude']))

            # New: Load contour height from rendering section
            self.contour_height.set(str(config['rendering']['contour_height']))

            self.gurumaps.set(config.get('gurumaps', True))
            self.export_passes.set(config.get('exportPasses', False))
            self.reset_results.set(config.get('reset_results', True))
            self.clean_temporary_files.set(
                config.get('clean_temporary_files', True))

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to load configuration: {str(e)}")

    def save_config(self):
        """Save current parameters to a YAML configuration file"""
        try:
            # Check if MountainCircles Folder has been filled
            if not self.main_folder.get().strip():
                messagebox.showerror(
                    "Error", "Please tell the app in the download tab where you put the MountainCircle folder before saving the configuration.")
                return

            self.validate_inputs()
            config = self.create_config_dict()

            # Create filename from config name
            filename = os.path.normpath(os.path.join(
                self.config_folder.get(), f"{self.name.get()}.yaml"))

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
                f.write(
                    f"  max_altitude: {int(config['calculation_parameters']['max_altitude'])}\n")
                f.write("\n")

                # Write rendering section
                f.write("rendering:\n")
                f.write(
                    f"  contour_height: {int(config['rendering']['contour_height'])}\n")
                f.write("\n")

                # Write boolean parameters
                f.write(f"gurumaps: {str(config['gurumaps']).lower()}\n")
                f.write(
                    f"exportPasses: {str(config['exportPasses']).lower()}\n")
                f.write(
                    f"reset_results: {str(config['reset_results']).lower()}\n")
                f.write(
                    f"clean_temporary_files: {str(config['clean_temporary_files']).lower()}\n")
                f.write("\n")

                # Write merged_output_name
                f.write(
                    f"merged_output_name: {config['merged_output_name']}\n")

            # Refresh the dropdown list after saving and pass the name of the just-saved config
            self.refresh_yaml_list(active_config=os.path.basename(filename))
            messagebox.showinfo("Success", "Configuration saved successfully!")

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to save configuration: {str(e)}")

    def create_config_dict(self):
        """Create a configuration dictionary from GUI inputs with ordered keys matching full.yaml"""
        from collections import OrderedDict

        config = OrderedDict([
            ("name", self.name.get() + " "),  # Add space to match format

            ("input_files", OrderedDict([
                ("airfield_file", self.airfield_path.get()),
                ("topography_file", self.topo_path.get()),
                ("CRS_file", self.topo_CRSfile.get()),
                ("result_folder", self.result_path.get()),
                ("compute", self.calc_script.get()),
                ("mapcssTemplate", os.path.normpath(os.path.join(
                    self.GMstyles_folder.get(), "circlesAndAirfields.mapcss")))
            ])),

            ("CRS", OrderedDict([
                ("name", "custom"),
                ("definition", self.input_crs.get())
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
                ("contour_height", int(self.contour_height.get()))
            ])),

            ("gurumaps", self.gurumaps.get()),
            ("exportPasses", self.export_passes.get()),
            ("reset_results", self.reset_results.get()),
            ("clean_temporary_files", self.clean_temporary_files.get()),

            ("merged_output_name", self.merged_output_name.get())
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
        # Validate CRS file
        try:
            crs_file_path = self.topo_CRSfile.get()

            # Read the CRS value from the file (which should contain only one line)
            with open(crs_file_path, "r") as f:
                self.input_crs.set(f.readline().strip())
        except Exception as e:
            raise ValueError(f"Unable to read CRS file: {str(e)}")

    def run_processing(self):
        """Run the main processing with current parameters"""
        try:
            # Check if MountainCircles Folder and Calculation Script fields have been filled
            missing_fields = []
            if not self.main_folder.get().strip():
                missing_fields.append("MountainCircles Folder")
            if not self.calc_script.get().strip():
                missing_fields.append("Calculation Script")
            if missing_fields:
                messagebox.showerror("Error",
                                     "The following field(s) are missing on the download tab: " + ", ".join(missing_fields))
                return

            self.validate_inputs()
            config = self.create_config_dict()

            # Create temporary config file
            temp_config_path = os.path.normpath(os.path.join(
                self.config_folder.get(), "temp_config.yaml"))

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
                f.write(
                    f"  max_altitude: {int(config['calculation_parameters']['max_altitude'])}\n")
                f.write("\n")

                f.write("rendering:\n")
                f.write(
                    f"  contour_height: {int(config['rendering']['contour_height'])}\n")
                f.write("\n")

                f.write(f"gurumaps: {str(config['gurumaps']).lower()}\n")
                f.write(
                    f"exportPasses: {str(config['exportPasses']).lower()}\n")
                f.write(
                    f"reset_results: {str(config['reset_results']).lower()}\n")
                f.write(
                    f"clean_temporary_files: {str(config['clean_temporary_files']).lower()}\n")
                f.write("\n")

                f.write(
                    f"merged_output_name: {config['merged_output_name']}\n")

            # Disable the run button while processing
            self.run_button.state(['disabled'])

            # Start processing in a separate thread
            thread = threading.Thread(
                target=lambda: self.process_data(temp_config_path))
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def process_data(self, config_path):
        """Run the main processing function with stdout/stderr redirected,
        and poll the output queue for messages from worker processes."""
        import queue  # Needed to catch the Empty exception

        # Save original stdout and stderr for later restoration
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # Redirect stdout and stderr to the status text widget
        sys.stdout = MountainCirclesGUI.TextRedirector(self.status_text)
        sys.stderr = MountainCirclesGUI.TextRedirector(self.status_text)

        # Create a manager and use a managed queue for safe sharing between processes
        manager = multiprocessing.Manager()
        output_queue = manager.Queue()

        def poll_queue():
            try:
                while True:
                    msg = output_queue.get_nowait()
                    self.status_text.insert(tk.END, msg)
                    self.status_text.see(tk.END)
            except queue.Empty:
                pass
            except BrokenPipeError:
                # The pipe has been closed (likely because the manager shut down),
                # so stop polling.
                return
            except Exception as e:
                print("Error polling output queue:", str(e))
                return
            # Schedule the next poll in 100ms
            self.root.after(100, poll_queue)

        # Start polling the queue
        self.root.after(100, poll_queue)

        try:
            multiprocessing.freeze_support()
            # Pass the shared output_queue to your launch function
            launch.main(config_path, output_queue)
            self.root.after(0, self.processing_complete)
        except Exception as e:
            error_message = str(e)  # Capture the error message
            self.root.after(0, lambda: self.processing_error(error_message))
        finally:
            # Restore the original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            # Clean up the temporary config file if it exists
            # if os.path.exists(config_path):
            #     os.remove(config_path)
            # Shut down the manager; subsequent queue access will raise errors,
            # but our poll_queue function catches those.
            manager.shutdown()

    def processing_complete(self):
        """Called when processing is complete"""
        self.run_button.state(['!disabled'])
        messagebox.showinfo("Success", "Processing completed successfully!")

    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.run_button.state(['!disabled'])
        messagebox.showerror(
            "Error", f"An error occurred during processing:\n{error_message}")

    def clear_log(self):
        """Clear the status text widget"""
        self.status_text.delete(1.0, tk.END)

    def open_results_folder(self):
        """Open the results folder in the system's file explorer"""
        result_path = self.result_path.get()
        if not result_path:
            messagebox.showwarning(
                "Warning", "Please select a result folder first.")
            return

        if not os.path.exists(result_path):
            messagebox.showwarning(
                "Warning", "Results folder does not exist yet.")
            return

        # Open folder in the default file explorer
        if sys.platform == 'darwin':  # macOS
            subprocess.run(['open', result_path])
        elif sys.platform == 'win32':  # Windows
            os.startfile(result_path)
        else:  # Linux
            subprocess.run(['xdg-open', result_path])

    def convert_cup_file(self):
        """Convert CUP file to CSV using cupConvert.py logic"""
        input_path = self.cup_input_path.get()
        output_path = self.cup_output_path.get()

        if not input_path or not output_path:
            messagebox.showerror(
                "Error", "Please select both input and output files.")
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

    def process_passes(self):
        """Process mountain passes using process_passes.py logic,
        redirecting stdout and stderr to the status text widget and switching to the Run tab."""
        # Activate the Run tab so that the output is visible
        self.notebook.select(self.run_tab)
        # Clear the current log
        self.clear_log()

        # Get required paths from the UI fields
        root_folder = self.process_passes_root_path.get()
        mountain_passes_path = self.ref_mountain_passes_path.get()
        crs_file_path = self.process_passes_CRSfile.get()

        if not all([root_folder, mountain_passes_path, crs_file_path]):
            messagebox.showerror("Error", "Please select all required paths.")
            return

        # Read the CRS value from the file (which should contain only one line)
        try:
            with open(crs_file_path, "r") as f:
                input_crs = f.readline().strip()
        except Exception as e:
            messagebox.showerror("Error", f"Unable to read CRS file: {str(e)}")
            return

        # Create output directory in the parent folder
        output_dir = os.path.normpath(os.path.join(root_folder, "processed_passes"))
        os.makedirs(output_dir, exist_ok=True)

        # Set intermediate and output file paths
        intermediate_path = os.path.normpath(os.path.join(output_dir, "intermediate_passes.geojson"))
        output_path = os.path.normpath(os.path.join(output_dir, "processed_passes.geojson"))

        # Run passes processing in a separate thread so the UI remains responsive.
        thread = threading.Thread(
            target=self.run_process_passes,
            args=(root_folder, input_crs, intermediate_path,
                  mountain_passes_path, output_path)
        )
        thread.daemon = True
        thread.start()

    def run_process_passes(self, root_folder, input_crs, intermediate_path, mountain_passes_path, output_path):
        """Worker function to run process passes with stdout and stderr redirected to the status text widget."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # Redirect stdout and stderr to the status text widget
        sys.stdout = MountainCirclesGUI.TextRedirector(self.status_text)
        sys.stderr = MountainCirclesGUI.TextRedirector(self.status_text)
        try:
            from utils.process_passes import process_passes
            process_passes(root_folder, input_crs, intermediate_path,
                           mountain_passes_path, output_path)
            # Use after() to schedule GUI updates in the main thread
            self.root.after(0, lambda: (
                self.status_text.insert(
                    tk.END, "Passes processed successfully!\n"),
                self.status_text.see(tk.END)
            ))
        except Exception as e:
            self.root.after(0, lambda: (
                self.status_text.insert(
                    tk.END, f"Failed to process passes: {str(e)}\n"),
                self.status_text.see(tk.END)
            ))
        finally:
            # Restore the original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    def toggle_help_section(self, button, help_frame):
        """Toggle the visibility of the help section"""
        self.help_visible = not self.help_visible
        if self.help_visible:
            help_frame.grid()
            button.configure(text="Hide Help ▲")
        else:
            help_frame.grid_remove()
            button.configure(text="Show Help ▼")

    def on_close(self):
        """Handler for app close; make sure settings are saved."""
        self.save_settings()
        self.root.destroy()

    def load_settings(self):
        """Load settings from the config file and update variables."""
        settings = load_settings()
        if "user_data_folder" in settings and "calc_script" in settings:
            self.main_folder.set(settings["user_data_folder"])
            self.calc_script.set(settings["calc_script"])
            print("Loaded data folder:", settings["user_data_folder"])
            print("Loaded calculation script:", settings["calc_script"])
            if self.main_folder.get() and self.calc_script.get():
                self.notebook.select(self.run_tab)

        else:
            print("You need to fill up the two fields on the download tab to run any calculation.")

    def save_settings(self):
        """Save current settings to the config file."""
        settings = {
            "user_data_folder": self.main_folder.get(),
            "calc_script": self.calc_script.get()
        }
        save_settings(settings)
        print("Saved settings:", settings)

    class TextRedirector:
        """Redirect stdout and stderr to the text widget with thread safety."""

        def __init__(self, widget):
            self.widget = widget

        def write(self, s):
            # Schedule the GUI update in the main thread
            self.widget.after(0, self.widget.insert, tk.END, s)
            self.widget.after(0, self.widget.see, tk.END)

        def flush(self):
            pass


def main():
    root = tk.Tk()
    app = MountainCirclesGUI(root)
    root.mainloop()


if __name__ == "__main__":
    import sys
    import multiprocessing
    import os
    import traceback

    # This call is required for frozen applications
    multiprocessing.freeze_support()

    # Only call set_executable for the main process
    if getattr(sys, 'frozen', False) and sys.platform == 'win32':
        try:
            multiprocessing.set_executable(sys.executable)
        except Exception as e:
            # Log the exception to a file (since using --noconsole means you won't see it)
            with open(os.path.normpath(os.path.join(os.getcwd(), "error.log")), "w") as error_file:
                traceback.print_exc(file=error_file)

    main()