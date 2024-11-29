#ifndef PARAMS_H
#define PARAMS_H

#include <cstddef>
#include <string>
#include <stdexcept>
#include <iostream>
#include "cell.h"
using namespace std;

struct Params {
    size_t global_ncols,global_nrows;
    float homex, homey, finesse, distSol, securite, 
        nodataltitude,cellsize_m,cellsize_over_finesse, 
        xllcorner, yllcorner;
    string output_path, topology, exportPasses;

    Params(int argc, char* argv[]) {
        if (argc < 10) {
            throw runtime_error("Not enough arguments provided. Expected format: ./compute homex homey finesse distSol securite nodataltitude output_path topology");
        }
        // Convert arguments to appropriate types
        homex = stof(argv[1]);
        homey = stof(argv[2]);
        finesse = stoi(argv[3]);
        distSol = stoi(argv[4]);
        securite = stoi(argv[5]);
        nodataltitude = stoi(argv[6]);
        output_path = argv[7];
        topology = argv[8];
        exportPasses = argv[9];
        // Convert to lowercase
        std::transform(exportPasses.begin(), exportPasses.end(), exportPasses.begin(),
                       [](unsigned char c){ return std::tolower(c); });

        // Use std::string comparison methods
        if (exportPasses != "true" && exportPasses != "false" && 
            exportPasses != "0" && exportPasses != "1") {
            std::cout << "Received value for exportPasses: " << exportPasses << std::endl;
            throw std::runtime_error("Invalid value for exportPasses. Expected 'true', 'false', '0', or '1'.");
        }
    }
};

#endif // PARAMS_H