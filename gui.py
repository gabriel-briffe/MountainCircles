import os
import sys
import subprocess
import threading
import multiprocessing
import webbrowser
from src.shortcuts import normJoin
from src.use_case_settings import Use_case


import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from app_settings import AppSettings
from utils.cupConvert import convert_coord
import launch,launch2


class MountainCirclesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mountain Circles")
        self.root.resizable(True, True)
        self.root.geometry("1200x1200")
        
        # Create a temporary log buffer to capture prints before the status text widget is created.
        self._log_buffer = []
        class BufferRedirector:
            def __init__(self, buffer_list):
                self.buffer = buffer_list
            def write(self, s):
                self.buffer.append(s)
            def flush(self):
                pass
        
        temp_redirector = BufferRedirector(self._log_buffer)
        sys.stdout = temp_redirector
        sys.stderr = temp_redirector
        
        # Variables to store settings
        self.data_folder_path = tk.StringVar(value="")
        self.calc_script = tk.StringVar(value="")
        self.region = tk.StringVar()
        self.use_case_name = tk.StringVar()
        self.use_case_dropdown_var = tk.StringVar()

        self.current_use_case_object = None

        # Create our AppSettings instance (which loads from ~/.mountaincircles.yaml by default)
        self.app_settings = AppSettings()

        # Populate interface fields with the saved settings (if they exist)
        self.populate_settings()

        print("-------welcome here---------")


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
        self.airfield_path = tk.StringVar(value="")
        self.topo_path = tk.StringVar(value="")
        self.topo_CRSfile_path = tk.StringVar(value="")
        self.glide_ratio = tk.StringVar(value="")
        self.ground_clearance = tk.StringVar(value="")
        self.circuit_height = tk.StringVar(value="")
        self.max_altitude = tk.StringVar(value="")
        self.contour_height = tk.StringVar(value="")
        self.delete_previous_calculation = tk.BooleanVar(value=False)
        self.gurumaps_styles = tk.BooleanVar(value=False)
        self.export_passes = tk.BooleanVar(value=False)
        self.clean_temporary_raster_files = tk.BooleanVar(value=False)
        self.beta = tk.BooleanVar(value=False)

        # self.input_crs = ""
        # self.GMstyles_folder_path = ""
        # self.result_config_path = ""
        self.ref_mountain_passes_path = tk.StringVar(value="")
        self.cup_input_path = tk.StringVar(value="")
        self.cup_output_path = tk.StringVar(value="")
        self.process_passes_CRSfile = tk.StringVar(value="")
        # --- New instance variables for generate_map.py parameters ---
        self.map_input_topo = tk.StringVar(value="")
        self.map_output_mbtiles = tk.StringVar(value="")
        self.map_bounds = tk.StringVar(value="")       # if empty, default will be used
        self.map_z_factor_slopes = tk.StringVar(value="1.4")      # default value is "1"
        self.map_z_factor_shades = tk.StringVar(value="2")      # default value is "1"
        self.map_azimuth = tk.StringVar(value="315")       # default value is "0"
        self.map_altitude = tk.StringVar(value="45")      # default value is "0"
        # self.merged_output_name = "aa"
        self.help_process_passes_filepath = ""
        self.help_run_filepath = ""
        # Setup tabs
        self.setup_download_tab()
        self.setup_run_tab()
        self.setup_utilities_tab()
        # self.load_settings()   # now using AppSettings instead of cload_settings
        if not self.data_folder_path.get() or not self.calc_script.get():
            print("You need to fill up the two fields on the download tab to run any calculation.")
        else:
            self.notebook.select(self.run_tab)
            
        # If a saved use case exists in AppSettings then update and populate the fields automatically
        if self.app_settings.use_case:
            self.refresh_use_case_dropdown(active_use_case=self.app_settings.use_case)
            # Set the dropdown variable to the saved use case
            self.use_case_dropdown_var.set(self.app_settings.use_case)
            # Automatically trigger the loading and population of fields
            self.on_use_case_select()


    def populate_settings(self):
        """
        Populate the GUI input fields with stored settings.
        On a fresh start, these will be empty; otherwise, the data_folder, calculation script,
        and region fields will be pre-filled.
        """
        if self.app_settings.data_folder_path:
            self.data_folder_path.set(self.app_settings.data_folder_path)
        if self.app_settings.calc_script:
            self.calc_script.set(self.app_settings.calc_script)
        if self.app_settings.region:
            self.region.set(self.app_settings.region)


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
        ttk.Label(param_frame, text="the MountainCircles folder:").grid(
            row=1, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.data_folder_path).grid(
            row=1, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Browse", command=lambda: self.browse_directory(
            "MountainCircles Folder", self.data_folder_path)).grid(row=1, column=2)

        # Calculation script
        ttk.Label(param_frame, text="the calculation script:").grid(
            row=3, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.calc_script).grid(
            row=3, column=1, padx=5, sticky="ew")
        
        # # Region dropdown menu below the calculation script section.
        # ttk.Label(param_frame, text="Region:").grid(row=5, column=0, sticky="w")
        # self.region_dropdown = ttk.Combobox(
        #     param_frame,
        #     textvariable=self.region,
        #     values=self.app_settings.regions,
        #     state="readonly"
        # )
        # self.region_dropdown.grid(row=5, column=1, padx=5, sticky="ew")

        param_frame.grid_columnconfigure(1, weight="1")

    def setup_run_tab(self):
        """Setup the Run tab with a simple layout using only frames."""
        # Create a main frame that fills the Run tab
        main_frame = ttk.Frame(self.run_tab, padding="5")
        main_frame.pack(expand=True, fill="both")
        main_frame.pack_propagate(False)

        # Create a frame (or label frame) at the top for Region and Use Case selections
        use_case_frame = ttk.LabelFrame(main_frame, padding="5")
        use_case_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Region Dropdown (populated from app_settings.regions)
        ttk.Label(use_case_frame, text="Select Region:").grid(
            row=0, column=0, padx=5, sticky="ew")
        self.region_dropdown = ttk.Combobox(
            use_case_frame,
            values=self.app_settings.regions,  # Using regions from app_settings
            width=30,
            textvariable=self.region,  # Ensure self.region is a tk.StringVar
            state="readonly"
        )
        self.region_dropdown.grid(row=0, column=1, padx=5, sticky="ew")
        self.region_dropdown.bind("<<ComboboxSelected>>", self.on_region_select)

        # Use Case Dropdown (populated from app_settings.use_cases)
        ttk.Label(use_case_frame, text="Select Use Case:").grid(
            row=1, column=0, padx=5, sticky="ew")
        self.use_case_dropdown = ttk.Combobox(
            use_case_frame,
            values=self.app_settings.use_cases,  # Use cases provided by app_settings
            width=30,
            textvariable=self.use_case_dropdown_var,  # Separate variable for dropdown
            state="readonly"
        )
        self.use_case_dropdown.grid(row=1, column=1, padx=5, sticky="ew")
        self.use_case_dropdown.bind("<<ComboboxSelected>>", self.on_use_case_select)

        # -----------------------------------------------------------------------
        # Parameter input frame
        param_frame = ttk.LabelFrame(main_frame, text="Use Case Parameters :", padding="5")
        param_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Use Case name and Save button
        ttk.Label(param_frame, text="Use Case name:").grid(row=1, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.use_case_name).grid(row=1, column=1, padx=5, sticky="ew")
        ttk.Button(param_frame, text="Save Use Case", command=self.save_use_case).grid(row=1, column=2)

        # Airfield file selection
        ttk.Label(param_frame, text="Airfield File:").grid(row=2, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.airfield_path).grid(row=2, column=1, padx=5, sticky="ew")
        airfield_buttons_frame = ttk.Frame(param_frame)
        airfield_buttons_frame.grid(row=2, column=2, sticky="w")
        ttk.Button(airfield_buttons_frame, text="Browse", command=lambda: self.browse_file("Airfield", self.airfield_path)).grid(row=0, column=0, padx=2)
        ttk.Button(airfield_buttons_frame, text="Open/edit", command=lambda: self.open_file("Airfield")).grid(row=0, column=1, padx=2)

        # Glide Parameters Section
        ttk.Label(param_frame, text="Glide Parameters", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky="w", pady=(15, 5))
        ttk.Label(param_frame, text="Glide Ratio:").grid(row=4, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.glide_ratio, width=10).grid(row=4, column=1, sticky="w", padx=5)

        # Ground clearance
        ttk.Label(param_frame, text="Ground Clearance (m):").grid(
            row=5, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.ground_clearance,
                  width=10).grid(row=5, column=1, sticky="w", padx=5)

        # Circuit height
        ttk.Label(param_frame, text="Circuit Height (m):").grid(
            row=6, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.circuit_height,
                  width=10).grid(row=6, column=1, sticky="w", padx=5)

        # Max altitude
        ttk.Label(param_frame, text="Max Altitude (m):").grid(
            row=7, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.max_altitude,
                  width=10).grid(row=7, column=1, sticky="w", padx=5)

        # Additional Options Section
        ttk.Label(param_frame, text="Additional Options", font=(
            'Arial', 10, 'bold')).grid(row=8, column=0, sticky="w", pady=(15, 5))

        # New Field: Contour Height
        ttk.Label(param_frame, text="Altitude delta between circles (m):").grid(
            row=9, column=0, sticky="w")
        ttk.Entry(param_frame, textvariable=self.contour_height,
                  width=10).grid(row=9, column=1, sticky="w", padx=5)

        # Checkboxes
        ttk.Checkbutton(param_frame, text="Erase previous calculation (if any)",
                        variable=self.delete_previous_calculation).grid(row=10, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Generate data files for Guru Maps",
                        variable=self.gurumaps_styles).grid(row=11, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Create mountain passes files",
                        variable=self.export_passes).grid(row=12, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Clean temporary files",
                        variable=self.clean_temporary_raster_files).grid(row=13, column=0, sticky="w")
        ttk.Checkbutton(param_frame, text="Beta", variable=self.beta).grid(row=14, column=0, sticky="w")

        param_frame.grid_columnconfigure(1, weight="1")

        # Control buttons frame
        control_btn_frame = ttk.Frame(main_frame)
        control_btn_frame.grid(row=15, column=0, columnspan=3, pady=10)
        
        ttk.Button(control_btn_frame, text="Clear Log",
                   command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # New Help button that opens the run help file
        ttk.Button(control_btn_frame, text="Help",
                   command=lambda: self.open_file("help_run")).pack(side=tk.LEFT, padx=5)
        
        self.run_button = ttk.Button(
            control_btn_frame, text="Run Processing", command=self.run_processing)
        self.run_button.pack(side=tk.LEFT, padx=5)
    
        self.open_results_button = ttk.Button(
            control_btn_frame, text="Open Results Folder", command=self.open_results_folder)
        self.open_results_button.pack(side=tk.LEFT, padx=5)

        # Added new "View Map" button – initially disabled until processing is complete.
        self.view_map_button = ttk.Button(control_btn_frame, text="View Map", command=self.view_map)
        self.view_map_button.pack(side=tk.LEFT, padx=5)
        self.view_map_button.config(state=tk.DISABLED)
        
        # Status display area
        ttk.Label(main_frame, text="Status:", font=('Arial', 10, 'bold')).grid(
            row=16, column=0, sticky="w", pady=5)
        self.status_text = tk.Text(main_frame)
        self.status_text.grid(
            row=17, column=0, columnspan=3, pady=5, sticky="nsew")
        scroller = ttk.Scrollbar(
            main_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        scroller.grid(row=17, column=3, sticky="ns")
        self.status_text['yscrollcommand'] = scroller.set
        
        # Flush any previously captured output from the temporary buffer into the status_text widget.
        for msg in self._log_buffer:
            self.status_text.insert(tk.END, msg)
        self.status_text.see(tk.END)
        
        # Now redirect stdout and stderr to the status_text widget
        sys.stdout = MountainCirclesGUI.TextRedirector(self.status_text)
        sys.stderr = MountainCirclesGUI.TextRedirector(self.status_text)
        
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(17, weight=1)

    def setup_utilities_tab(self):
        """Setup the Utilities tab with sections for various utilities."""
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

        # New action buttons (Open Help File and Process Passes)
        action_frame = ttk.Frame(process_passes_frame)
        action_frame.grid(row=3, column=0, columnspan=3, pady=10)
        ttk.Button(action_frame, text="Open Help File", command=lambda: self.open_file("Help_Passes")).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Process Passes", command=self.process_passes).pack(side=tk.LEFT, padx=5)

        process_passes_frame.grid_columnconfigure(1, weight=1)

        # -----------------------------------------------------------
        # Generate Map Section (MBTiles generation using generate_map.py)
        map_frame = ttk.LabelFrame(main_frame, text="Generate Map (MBTiles)", padding="5")
        map_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20)
        
        # Input Topo file
        ttk.Label(map_frame, text="Input Topo file:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_input_topo).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(map_frame, text="Browse", command=lambda: self.browse_file("Topo File", self.map_input_topo)).grid(row=0, column=2)

        # Output MBTiles file
        ttk.Label(map_frame, text="Output MBTiles file:").grid(
            row=1, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_output_mbtiles).grid(
            row=1, column=1, sticky="ew", padx=5)
        ttk.Button(map_frame, text="Browse", 
                   command=lambda: self.browse_save_file("MBTiles File", self.map_output_mbtiles, [("MBTiles files", "*.mbtiles")])
                  ).grid(row=1, column=2)

        # GeoJSON Bounds file field (modified label)
        ttk.Label(map_frame, text="Use this GeoJSON for bounds (optional):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_bounds).grid(row=2, column=1, sticky="ew", padx=5)
        ttk.Button(map_frame, text="Browse", command=lambda: self.browse_file("GeoJSON File", self.map_bounds)).grid(row=2, column=2)

        # Z-factor for slopes
        ttk.Label(map_frame, text="Z-factor for slopes:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_z_factor_slopes).grid(row=3, column=1, sticky="ew", padx=5)
        
        # Z-factor for shades
        ttk.Label(map_frame, text="Z-factor for shades:").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_z_factor_shades).grid(row=4, column=1, sticky="ew", padx=5)
        
        # Azimuth
        ttk.Label(map_frame, text="Azimuth:").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_azimuth).grid(row=5, column=1, sticky="ew", padx=5)
        
        # Altitude
        ttk.Label(map_frame, text="Altitude:").grid(row=6, column=0, sticky="w", pady=5)
        ttk.Entry(map_frame, textvariable=self.map_altitude).grid(row=6, column=1, sticky="ew", padx=5)
        
        # Generate Map button
        ttk.Button(map_frame, text="Generate Map", command=self.generate_map).grid(row=7, column=1, pady=10)
        
        map_frame.grid_columnconfigure(1, weight=1)

        main_frame.grid_columnconfigure(0, weight=1)

    def open_download_page(self):
        """Opens the system's default browser to the download page."""
        webbrowser.open(
            # Replace with the actual URL you want to open.
            "https://drive.google.com/drive/folders/1MeU_GSd5152h_8e1rB8i-fspA9_dqah-?usp=sharing")

    def browse_file(self, file_type, var, filetypes=None, initialdir=None):
        """Browse for a file and update the corresponding variable"""
        if initialdir is None:
            initialdir = self.data_folder_path.get()
        if file_type == "Calculation script":
            calc_script_dir = normJoin(self.data_folder_path.get(), "common files", "calculation script")
            if os.path.exists(calc_script_dir):
                initialdir = calc_script_dir
        elif file_type == "Airfield":
            region = self.region.get()
            if not region:
                messagebox.showwarning("Warning", "Region is not selected. Please select a region first.")
                return
            airfield_dir = normJoin(self.data_folder_path.get(), region, "airfield files")
            if os.path.exists(airfield_dir):
                initialdir = airfield_dir
            else:
                messagebox.showwarning("Warning", f"Airfield folder not found:\n{airfield_dir}")
                # fallback to the data folder path if the airfields folder is not found
                initialdir = self.data_folder_path.get()
        
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
                        # Assign the first .txt file to self.topo_CRSfile_path
                        self.topo_CRSfile_path.set(normJoin(directory, txt_files[0]))
                        print(
                            f"Automatically detected CRS file: {self.topo_CRSfile_path.get()}")
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
        # Use self.data_folder_path as the initial directory if it is set; otherwise, use the current working directory.
        initial_dir = self.data_folder_path.get() if self.data_folder_path.get() else os.getcwd()
        path = filedialog.askdirectory(
            title=f"Select {dir_type}", initialdir=initial_dir)
        if path:
            var.set(path)
            if dir_type == "MountainCircles Folder":
                self.app_settings.data_folder_path = path
                self.app_settings.save()
                # Update the region dropdown since app_settings.regions has changed.
                self.init_calc_and_regions()
                # Manually update the calculation script field in the GUI:

    def open_file(self, file_type):
        """Open a file with the system's default application.

        file_type: A string specifying which file to open.
                   "Airfield"    -> opens the airfield file using self.airfield_path.
                   "Help_Passes" -> opens the help file for passes using self.help_process_passes_filepath.
                   "help_run"    -> opens the help file for running using self.help_run_filepath.
        """
        if file_type == "Airfield":
            file_path = self.airfield_path.get()
            if not file_path:
                messagebox.showwarning("Warning", "Please select an airfield file first.")
                return
        elif file_type == "Help_Passes":
            file_path = self.help_process_passes_filepath
            if not file_path:
                messagebox.showwarning("Warning", "Help file is not set.")
                return
        elif file_type == "help_run":
            file_path = self.help_run_filepath
            if not file_path:
                messagebox.showwarning("Warning", "Help file for run is not set.")
                return
        else:
            messagebox.showerror("Error", f"Unknown file type: {file_type}")
            return

        if not os.path.exists(file_path):
            messagebox.showwarning("Warning", "Selected file does not exist.")
            return

        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', '-a', 'TextEdit', file_path])
            elif sys.platform == 'win32':  # Windows
                os.startfile(file_path)
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")


    def load_selected_use_case(self, event=None):
        """Load the selected use case YAML file using the Use_case class from use_case_settings.py and update GUI fields accordingly."""

        # Get the selected use case file (e.g. "MyUseCase.yaml")
        selected = self.use_case_dropdown_var.get()
        if not selected:
            return

        # Construct the full path to the selected YAML file
        file_path = normJoin(self.app_settings.configuration_files_path, selected)
        try:
            # Create a Use_case instance by loading the YAML file
            use_case_obj = Use_case(use_case_file=file_path)
            
            # Update GUI fields from the loaded use case
            self.airfield_path.set(use_case_obj.airfield_file_path)
            self.topo_path.set(use_case_obj.topography_file)
            self.topo_CRSfile_path.set(use_case_obj._crs_file_path)
            
            self.glide_ratio.set(use_case_obj.glide_ratio)
            self.ground_clearance.set(use_case_obj.ground_clearance)
            self.circuit_height.set(use_case_obj.circuit_height)
            self.max_altitude.set(use_case_obj.max_altitude)
            self.contour_height.set(use_case_obj.contour_height)
            
            # For checkboxes or boolean values:
            self.gurumaps_styles.set(use_case_obj.gurumaps_styles)
            self.export_passes.set(use_case_obj.exportPasses)
            self.delete_previous_calculation.set(use_case_obj.delete_previous_calculation)
            self.clean_temporary_raster_files.set(use_case_obj.clean_temporary_raster_files)

            # Save the selected use case into AppSettings
            self.app_settings.use_case = selected
            self.app_settings.save()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load use case: {e}")

    def save_use_case(self):
        """Save current parameters as a YAML use case file via the Use_case object."""
        try:
            # Check if MountainCircles Folder has been filled
            if not self.data_folder_path.get().strip():
                messagebox.showerror(
                    "Error",
                    "Please tell the app in the download tab where you put the MountainCircle folder before saving the use case."
                )
                return

            # Create a parameter dictionary for the Use_case object.
            params = {
                "data_folder_path": self.data_folder_path.get(),
                "region": self.region.get(),
                "use_case_name": self.use_case_name.get(),
                "airfield_file": self.airfield_path.get(),
                "calculation_script": self.calc_script.get(),
                "glide_ratio": int(self.glide_ratio.get()),
                "ground_clearance": int(self.ground_clearance.get()),
                "circuit_height": int(self.circuit_height.get()),
                "max_altitude": int(self.max_altitude.get()),
                "contour_height": int(self.contour_height.get()),
                "merged_prefix": "aa",
                "gurumaps_styles": self.gurumaps_styles.get(),
                "exportPasses": self.export_passes.get(),
                "delete_previous_calculation": self.delete_previous_calculation.get(),
                "clean_temporary_raster_files": self.clean_temporary_raster_files.get(),
            }

            # print("[DEBUG] Use case parameters:", params)

            # Create the Use_case object using parameters.
            use_case_obj = Use_case(params=params)
            
            # Use the object's own save method to write the YAML file.
            use_case_obj.save()

            # Refresh the use case dropdown with the new list.
            self.refresh_use_case_dropdown(active_use_case=use_case_obj.use_case_name)

            messagebox.showinfo("Success", "Use case saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save use case: {str(e)}")

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
            int(self.glide_ratio.get())
            int(self.ground_clearance.get())
            int(self.circuit_height.get())
            int(self.max_altitude.get())

        except ValueError:
            raise ValueError("All numeric parameters must be valid numbers")
        # Validate CRS file
        try:
            crs_file_path = self.topo_CRSfile_path.get()

            # Read the CRS value from the file (which should contain only one line)
            with open(crs_file_path, "r") as f:
                self.input_crs = f.readline().strip()
        except Exception as e:
            raise ValueError(f"Unable to read CRS file: {str(e)}")

    def run_processing(self):
        """Run the main processing with use case parameters.
        
        Instead of manually generating the YAML configuration,
        we now gather parameters and let the Use_case class handle path generation and saving.
        """
        # Shut down any previously running HTTP server before starting new processing
        if hasattr(self, 'httpd') and self.httpd:
            try:
                print("Shutting down previous HTTP server before starting new processing...")
                self.httpd.shutdown()
                self.httpd.server_close()
                self.server_thread.join(timeout=5)
            except Exception as e:
                print("Error shutting down previous server:", e)
            finally:
                self.httpd = None

        try:
            # Check for required fields (update field names as needed)
            missing_fields = []
            if not self.data_folder_path.get().strip():
                missing_fields.append("MountainCircles Folder")
            if not self.calc_script.get().strip():
                missing_fields.append("Calculation Script")
            if missing_fields:
                messagebox.showerror("Error", "Missing: " + ", ".join(missing_fields))
                return

            # Prepare parameters dictionary for the Use_case
            params = {
                "data_folder_path": self.data_folder_path.get(),
                "region": self.region.get(),
                "use_case_name": self.use_case_name.get(),
                "airfield_file": self.airfield_path.get(),
                "calculation_script": self.calc_script.get(),
                "glide_ratio": int(self.glide_ratio.get()),
                "ground_clearance": int(self.ground_clearance.get()),
                "circuit_height": int(self.circuit_height.get()),
                "max_altitude": int(self.max_altitude.get()),
                "contour_height": int(self.contour_height.get()),
                "merged_prefix": "aa",  # Adjust as needed
                "gurumaps_styles": self.gurumaps_styles.get(),
                "exportPasses": self.export_passes.get(),
                "delete_previous_calculation": self.delete_previous_calculation.get(),
                "clean_temporary_raster_files": self.clean_temporary_raster_files.get(),
            }

            # print("DEBUG: run_processing parameters:", params)

            # Create and save the use case using the Use_case class
            self.current_use_case_object = Use_case(params=params)
            self.current_use_case_object.save()

            # Retrieve the path of the newly created YAML file from the Use_case helper property
            config_path = normJoin(self.current_use_case_object.use_case_files_folder, f"{self.current_use_case_object.use_case_name}.yaml")

            # print("DEBUG: Config file will be generated at:", config_path)

            # Disable the run button until processing is finished
            self.run_button.config(state=tk.DISABLED)
            
            thread = threading.Thread(target=lambda: self.process_data(config_path))
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def process_data(self, config_path):
        """Run the main processing function with stdout/stderr redirected,
        and poll the output queue for messages from worker processes."""
        import queue  # Needed to catch the Empty exception

        # print("DEBUG: Starting process_data with config_path:", config_path)
        # if not os.path.exists(config_path):
            # print("DEBUG: WARNING - The config file does not exist at:", config_path)

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
                # print("DEBUG: Error polling output queue:", str(e))
                return
            # Schedule the next poll in 100ms
            self.root.after(100, poll_queue)

        # Start polling the queue
        self.root.after(100, poll_queue)

        try:
            multiprocessing.freeze_support()
            # Conditionally call launch2.main if beta is checked.
            if self.beta.get():
                launch2.main(config_path, output_queue)
            else:
                launch.main(config_path, output_queue)
            self.root.after(0, self.processing_complete)
        except Exception as e:
            error_message = str(e)  # Capture the error message
            # print("DEBUG: Exception in process_data:", error_message)
            self.root.after(0, lambda: self.processing_error(error_message))
        finally:
            # Restore the original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            manager.shutdown()

    def processing_complete(self):
        """Called when processing is complete"""
        # Re-enable the run button
        self.run_button.config(state=tk.NORMAL)
        print("Success", "Processing completed successfully!")
        
        self.calculation_result_folder = self.current_use_case_object.calculation_folder_path
        self.merged_layer_path = self.current_use_case_object.merged_output_filepath
        # print(f"on essaie d'ouvrir: {self.merged_layer_path}")
        self.launch_map_server()

    def launch_map_server(self):
        """Launch an HTTP server to serve the result folder (with an updated map.html),
        so that you can access all files in that folder from your browser.
        This version shuts down any previously active HTTP server and sets allow_reuse_address."""
        import http.server
        import socketserver
        import threading
        import os
        import webbrowser
        import shutil
        import functools
        from tkinter import messagebox

        port = 8000

        # Shut down any previously running HTTP server (if any)
        if hasattr(self, 'httpd') and self.httpd:
            try:
                print("Shutting down previous HTTP server...")
                self.httpd.shutdown()
                self.httpd.server_close()  # Ensure the socket is closed.
                self.server_thread.join(timeout=5)
            except Exception as e:
                print("Error shutting down previous server:", e)
        
        # Set this to allow the server to rebind to the same port.
        socketserver.TCPServer.allow_reuse_address = True

        # Get the result folder from your configuration (make sure it is set)
        if not os.path.exists(self.calculation_result_folder):
            messagebox.showerror("Error from launch_map_server()", "Calculation result folder does not exist.")
            return

        # Locate the original map.html using an absolute path (relative to the script)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        orig_map_path = normJoin(script_dir, "map.html")
        dest_map_path = normJoin(self.calculation_result_folder, "temp_map.html")

        # Get the merged layer path from your processing.
        # This should have been set during processing.
        merged_layer_path = self.current_use_case_object.merged_output_filepath
        # if merged_layer_path does not exist, warn user to run processing first
        if not os.path.exists(merged_layer_path):
            print("Run processing first.")
            return
        
        geojson_filename = os.path.basename(merged_layer_path)
        merged_layer_path = geojson_filename

        # --- Process sectors layer (new logic) ---
        sectors_file_path = self.current_use_case_object.sectors1_filepath
        sectors_geojson_filename = os.path.basename(sectors_file_path)
        sectors_file_path = sectors_geojson_filename

        # Merge the two HTML updates into one.
        # First, get the map bounds and then update the HTML file from the original map.html template.
        try:
            minx, miny, maxx, maxy = self.get_bounds()
            with open(orig_map_path, 'r') as f:
                content = f.read()

            # Replace the placeholder for bounds.
            content = content.replace("[[minx, miny], [maxx, maxy]]",
                                      f"[[{minx}, {miny}], [{maxx}, {maxy}]]")

            # Replace the placeholder for the merged layer file.
            content = content.replace("nameToReplace", merged_layer_path)
            print(f"Merged layer path: {merged_layer_path}")
            # Replace the placeholder for sectors file.
            content = content.replace("sectorsPlaceHolder", sectors_file_path)
            print(f"Sectors file path: {sectors_file_path}")

            content = content.replace("parametersPlaceholder", f"L/D {self.current_use_case_object.glide_ratio} - Ground {self.current_use_case_object.ground_clearance}m - Circuit Height {self.current_use_case_object.circuit_height}m")

            # Write the updated content once.
            with open(dest_map_path, 'w') as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update map.html: {str(e)}")
            return

        # Instead of os.chdir(result_folder), use the directory argument in the HTTP handler.
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.calculation_result_folder)
        try:
            self.httpd = socketserver.TCPServer(("", port), handler)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch server: {str(e)}")
            return

        def serve():
            print(f"Serving HTTP on localhost port {port} from {self.calculation_result_folder}")
            self.httpd.serve_forever()

        self.server_thread = threading.Thread(target=serve)
        self.server_thread.daemon = True
        self.server_thread.start()

        # Open the updated map file in the default browser.
        webbrowser.open(f"http://localhost:{port}/temp_map.html")

    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        # Re-enable the run button if there's an error
        self.run_button.config(state=tk.NORMAL)
        messagebox.showerror("Error", f"An error occurred during processing:\n{error_message}")

    def clear_log(self):
        """Clear the status text widget"""
        self.status_text.delete(1.0, tk.END)

    def open_results_folder(self):
        """Open the results folder in the system's file explorer"""
        result_path = self.current_use_case_object.calculation_folder_path
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
        output_dir = normJoin(root_folder, "processed_passes")
        os.makedirs(output_dir, exist_ok=True)

        # Set intermediate and output file paths
        intermediate_path = normJoin(output_dir, "intermediate_passes.geojson")
        output_path = normJoin(output_dir, "processed_passes.geojson")

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

        # Debug: Log the parameters for troubleshooting.
        # print("DEBUG: Running process_passes with parameters:")
        # print(f"DEBUG: root_folder: {root_folder}")
        # print(f"DEBUG: input_crs: {input_crs}")
        # print(f"DEBUG: intermediate_path: {intermediate_path}")
        # print(f"DEBUG: mountain_passes_path: {mountain_passes_path}")
        # print(f"DEBUG: output_path: {output_path}")

        # Redirect stdout and stderr to the status text widget
        sys.stdout = MountainCirclesGUI.TextRedirector(self.status_text)
        sys.stderr = MountainCirclesGUI.TextRedirector(self.status_text)
        try:
            from utils.process_passes import process_passes
            process_passes(root_folder, input_crs, intermediate_path,
                           mountain_passes_path, output_path)
            # Use after() to schedule GUI updates in the main thread
            self.root.after(0, lambda: (
                self.status_text.insert(tk.END, "Passes processed successfully!\n"),
                self.status_text.see(tk.END)
            ))
        except Exception as e:
            error_message = str(e)  # Store the message in a local variable
            # print("DEBUG: Exception encountered in run_process_passes:", error_message)
            self.root.after(0, lambda: (
                self.status_text.insert(tk.END, f"Failed to process passes: {error_message}\n"),
                self.status_text.see(tk.END)
            ))
        finally:
            # Restore the original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr


    def save_settings(self):
        """Save current settings using AppSettings."""
        self.app_settings.data_folder_path = self.data_folder_path.get()
        self.app_settings.calc_script = self.calc_script.get()
        self.app_settings.region = self.region.get()
        if hasattr(self, 'use_case_dropdown'):
            self.app_settings.use_case = self.use_case_dropdown_var.get()
        self.app_settings.save()
        print("Saved settings:", {
            "data_folder_path": self.app_settings.data_folder_path,
            "calc_script": self.app_settings.calc_script,
            "region": self.app_settings.region,
            "use_case": self.app_settings.use_case
        })

    def on_region_select(self, event):
        """Callback for when a region is selected in the dropdown."""
        selected_region = self.region_dropdown.get()
        if selected_region:
            self.app_settings.region = selected_region
            self.region.set(selected_region)
            # Optionally, update the use case dropdown:
            self.refresh_use_case_dropdown()
            # If no use cases exist for the selected region, clear the use case fields.
            if not self.app_settings.use_cases:
                self.clear_use_case_fields()

    def get_abs_path(self, path):
        """
        Given a file or folder path, return an absolute path based on the data folder.
        If the given path is already absolute, simply return a normalized version.
        """
        if path and not os.path.isabs(path) and self.data_folder_path.get():
            return normJoin(self.data_folder_path.get(), path)
        return os.path.normpath(path)

    def init_calc_and_regions(self):
        self.calc_script.set(self.app_settings.calc_script)

        """Initialize the region dropdown with the available regions from app_settings."""
        if hasattr(self, 'region_dropdown'):
            self.region_dropdown['values'] = self.app_settings.regions
            if self.app_settings.regions:
                self.region_dropdown.current(0)
                self.region.set(self.app_settings.regions[0])
                # Update the region property of app_settings accordingly.
                self.app_settings.region = self.app_settings.regions[0]

    def on_use_case_select(self, event=None):
        """Callback when a user selects a saved use case from the dropdown.
        This loads the saved use case and populates the fields, including updating
        the checkboxes and the use case name text field.
        
        Also, if the loaded use case already has a calculation result (i.e. if the
        use case provides a calculation result folder and a merged output file that exist on disk),
        the 'View Map' button is enabled. Otherwise, it is disabled.
        """
        selected = self.use_case_dropdown_var.get()
        if not selected:
            return

        # Update the AppSettings use_case property with the selected value and save the settings.
        self.app_settings.use_case = selected
        self.app_settings.save()

        # Construct the path to the use case file.
        use_case_dir = normJoin(self.data_folder_path.get(), self.region.get(), "use case files")
        use_case_file = normJoin(use_case_dir, selected)
        try:
            loaded_use_case = Use_case(use_case_file=use_case_file)
            self.current_use_case_object = loaded_use_case
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load use case: {str(e)}")
            return

        # Populate text and numerical fields from the loaded use case.
        self.use_case_name.set(loaded_use_case.use_case_name)
        self.airfield_path.set(loaded_use_case.airfield_file_path)
        self.glide_ratio.set(str(loaded_use_case.glide_ratio))
        self.ground_clearance.set(str(loaded_use_case.ground_clearance))
        self.circuit_height.set(str(loaded_use_case.circuit_height))
        self.max_altitude.set(str(loaded_use_case.max_altitude))
        self.contour_height.set(str(loaded_use_case.contour_height))

        # Update the checkboxes.
        self.gurumaps_styles.set(loaded_use_case.gurumaps_styles)
        self.export_passes.set(loaded_use_case.exportPasses)
        self.delete_previous_calculation.set(loaded_use_case.delete_previous_calculation)
        self.clean_temporary_raster_files.set(loaded_use_case.clean_temporary_raster_files)

        # If the loaded use case contains previous calculation results, set the corresponding attributes.
        if hasattr(loaded_use_case, 'calculation_folder_path'):
            self.calculation_result_folder = loaded_use_case.calculation_folder_path
        else:
            self.calculation_result_folder = None

        if hasattr(loaded_use_case, 'merged_output_filepath'):
            self.merged_layer_path = loaded_use_case.merged_output_filepath
        else:
            self.merged_layer_path = None

        # Verify that the calculation result folder exists and that the merged output file exists,
        # then enable the "View Map" button accordingly.
        if (self.calculation_result_folder and os.path.exists(self.calculation_result_folder) and
            self.merged_layer_path and os.path.exists(self.merged_layer_path)):
            self.view_map_button.config(state=tk.NORMAL)
        else:
            self.view_map_button.config(state=tk.DISABLED)

        print(f"Loaded use case: {loaded_use_case.use_case_name}")


    def refresh_use_case_dropdown(self, active_use_case=None):
        """Refresh the list of saved use cases in the dropdown.

        This updates the dropdown with filenames or use case names from settings.
        It does not change the text in the new use case input field (self.use_case_name).
        """
        use_cases = self.app_settings.use_cases
        self.use_case_dropdown['values'] = use_cases
        if active_use_case and active_use_case in use_cases:
            # If you want to show the active saved use case in the dropdown, update it.
            self.use_case_dropdown_var.set(active_use_case)
        elif use_cases:
            # Optionally, clear the dropdown selection by setting an empty string:
            self.clear_use_case_fields()

    def clear_use_case_fields(self):
        """
        Clear all fields related to a use case.
        This way, if no use case is available for the new region,
        previous data from another region won't remain.
        """
        self.use_case_dropdown_var.set("")
        self.use_case_name.set("")  # the new/editable field for use case name
        # Optionally clear other fields related to the use case:
        self.airfield_path.set("")
        self.glide_ratio.set("")
        self.ground_clearance.set("")
        self.circuit_height.set("")
        self.max_altitude.set("")
        self.contour_height.set("")

    def view_map(self):
        """View the map of the current use case if a calculation has been done.
        
        If the calculation results exist (i.e. processing has been run and 
        both result folder and merged layer path have been set), then 
        launch_map_server() is called. Otherwise, notify the user.
        """
        if (hasattr(self, "calculation_result_folder") and self.calculation_result_folder and
            hasattr(self, "merged_layer_path") and self.merged_layer_path):
            self.launch_map_server()
        else:
            messagebox.showinfo("No Calculation",
                                "No calculation has been done for the current use case.\n"
                                "Please run processing first.")

    def generate_map(self):
        """Call generate_map.py functionality via direct import in a separate thread.
        Activate the Run tab to display console output."""
        # Activate the Run tab so that redirected console output is visible.
        self.notebook.select(self.run_tab)
        self.clear_log()  # Clear any existing text in the status box.
        
        input_topo = self.map_input_topo.get()
        output_mbtiles = self.map_output_mbtiles.get()
        # Retrieve the GeoJSON bounds file (if provided)
        bounds = self.map_bounds.get().strip() or None
        
        try:
            z_factor_slopes = float(self.map_z_factor_slopes.get().strip())
        except ValueError:
            z_factor_slopes = 1.4
        try:
            z_factor_shades = float(self.map_z_factor_shades.get().strip())
        except ValueError:
            z_factor_shades = 2
        try:
            azimuth = float(self.map_azimuth.get().strip())
        except ValueError:
            azimuth = 315
        try:
            altitude = float(self.map_altitude.get().strip())
        except ValueError:
            altitude = 45

        # Validate required fields.
        if not input_topo or not output_mbtiles:
            messagebox.showerror("Error", "Input Topo and Output MBTiles files are required.")
            return

        # Launch map generation in a separate thread.
        thread = threading.Thread(
            target=self.run_generate_map_thread,
            args=(input_topo, output_mbtiles, bounds, z_factor_slopes, z_factor_shades, azimuth, altitude)
        )
        thread.daemon = True
        thread.start()

    def run_generate_map_thread(self, input_topo, output_mbtiles, bounds, z_factor_slopes, z_factor_shades, azimuth, altitude):
        """Worker function running in a separate thread to call run_generate_map()."""
        try:
            from utils.generate_map import run_generate_map
            run_generate_map(input_topo, output_mbtiles, bounds=bounds,
                             z_factor_slopes=z_factor_slopes, z_factor_shades=z_factor_shades, azimuth=azimuth, altitude=altitude)
            # Schedule a success message to be shown from the main thread.
            self.root.after(0, lambda: messagebox.showinfo("Success", "Map generated successfully!"))
        except Exception as e:
            # Schedule an error message to be shown from the main thread.
            self.root.after(0, lambda: messagebox.showerror("Error", f"Map generation failed: {e}"))

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

    def get_bounds(self):
        #open airfield csv file and get minx, miny, maxx, maxy
        airfield_path = self.airfield_path.get()
        df = pd.read_csv(airfield_path)
        minx = df['x'].min()
        miny = df['y'].min()
        maxx = df['x'].max()
        maxy = df['y'].max()
        return minx, miny, maxx, maxy

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
            with open(normJoin(os.getcwd(), "error.log"), "w") as error_file:
                traceback.print_exc(file=error_file)

    main()