import os
import platform
import yaml
from src.shortcuts import normJoin

DEFAULT_SETTINGS_FILE = os.path.normpath(os.path.expanduser("~/.mountaincircles.yaml"))

class AppSettings:
    def __init__(self, settings_file=DEFAULT_SETTINGS_FILE):
        self.settings_file = settings_file
        self.data = {
            "data_folder_path": None,
            "calc_script": None,
            "region": None,
            "use_case": None,
        }
        # These attributes will hold our cached regions and use cases.
        self._regions = []
        self._use_cases = []
        self.load()

    def load(self):
        """Load settings from file if it exists."""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                self.data.update(yaml.safe_load(f) or {})
            print("Loaded settings data:")
            for key, value in self.data.items():
                print(f"{key}: {value}")
        else:
            print("No settings found")
        # Update regions and use cases based on the data folder.
        self._regions = self.find_regions()
        if self.data.get("region"):
            self._use_cases = self.find_use_cases()
        else:
            self._use_cases = []

    def save(self):
        """Save settings to file."""
        with open(self.settings_file, "w") as f:
            yaml.safe_dump(self.data, f)

    def find_calc_script(self):
        """Find the calc script in the data folder path."""
        calc_script_path = normJoin(self.data_folder_path, "common files", "calculation script")
        if os.path.exists(calc_script_path):
            os_name=platform.system()
            architecture=platform.machine()
            print(f"Operating System: {os_name}")
            print(f"Architecture: {architecture}")
            # Retrieve system name and architecture using the platform module
            # For macOS ARM64
            if os_name == "Darwin" and architecture in ["arm64", "ARM64", "aarch64"]:
                self.calc_script = "compute_mac_arm64"
            # For macOS x86_64
            if os_name == "Darwin" and architecture in ["AMD64", "x86_64"]:
                self.calc_script = "compute_mac_x86_64"
            # For Windows ARM64
            if os_name == "Windows" and architecture in ["arm64", "ARM64", "aarch64"]:
                self.calc_script = "compute_windows_arm64.exe"
            # For Windows x86_64
            if os_name == "Windows" and architecture in ["AMD64", "x86_64"]:
                self.calc_script = "compute_windows_AMD64.exe"
            print(f'found your calculation script: {self.calc_script}')
        else:
            print(f"folder does not exists{calc_script_path}")

    @property
    def data_folder_path(self):
        return self.data.get("data_folder_path")

    @data_folder_path.setter
    def data_folder_path(self, value):
        self.data["data_folder_path"] = value
        print("Setting data_folder_path to:", value)  # Debug print
        self.find_calc_script()
        # Find and store region folders (excluding "common files")
        self._regions = self.find_regions()
        print("Found regions:", self._regions)
        self.save()

    @property
    def calc_script(self):
        return self.data.get("calc_script")

    @calc_script.setter
    def calc_script(self, value):
        self.data["calc_script"] = value
        self.save()

    @property
    def region(self):
        """Return the current region."""
        return self.data.get("region")

    @region.setter
    def region(self, value):
        """Set a new region, save the settings, and update use cases accordingly."""
        self.data["region"] = value
        self.save()
        self._use_cases = self.find_use_cases()

    @property
    def use_case(self):
        return self.data.get("use_case")

    @use_case.setter
    def use_case(self, value):
        self.data["use_case"] = value
        self.save()

    @property
    def configuration_files_path(self):
        """
        Returns the path to the "configuration files" folder for the current region.
        If both data_folder_path and region are set, it constructs:
            data_folder_path/region/configuration files
        Otherwise, it prints a message and returns None.
        """
        if self.data_folder_path and self.region:
            return normJoin(self.data_folder_path, self.region, "configuration files")
        else:
            print("Data folder path or region not set; cannot determine configuration files path.")
            return None

    def find_regions(self):
        """
        Return a list of region folders in the root of data_folder_path,
        excluding the "common files" folder.
        """
        regions = []
        path = self.data.get("data_folder_path")
        if path and os.path.exists(path):
            for folder in os.listdir(path):
                full_path = normJoin(path, folder)
                if os.path.isdir(full_path) and folder.lower() != "common files":
                    regions.append(folder)
        else:
            print("The data folder path does not exist")
        return regions

    def find_use_cases(self):
        """
        Return a list of use case YAML files within the selected region folder.
        Expected location:
            data_folder_path/<region>/use case files/
        """
        use_cases = []
        data_folder_path = self.data.get("data_folder_path")
        region = self.data.get("region")
        if data_folder_path and region:
            region_path = normJoin(data_folder_path, region)
            use_case_folder = normJoin(region_path, "use case files")
            if os.path.exists(use_case_folder):
                for fname in os.listdir(use_case_folder):
                    full_path = normJoin(use_case_folder, fname)
                    if os.path.isfile(full_path) and fname.lower().endswith(".yaml"):
                        use_cases.append(fname)
            else:
                print("The 'use case files' folder does not exist in region:", region)
        else:
            print("Region not set or data folder path missing.")
        return use_cases

    @property
    def regions(self):
        """Property that returns the updated list of regions."""
        self._regions = self.find_regions()
        return self._regions

    @property
    def use_cases(self):
        """Property that returns the updated list of use case YAML files for the current region."""
        if self.data.get("region"):
            self._use_cases = self.find_use_cases()
        else:
            self._use_cases = []
        return self._use_cases 