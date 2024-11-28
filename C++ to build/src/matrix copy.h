#ifndef MATRIX_H
#define MATRIX_H

#include <cstddef>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <limits>
#include <iostream>
#include "cell.h"  // Assuming Cell class is defined in cell.h
using namespace std;

class Matrix {
public:
    vector<vector<Cell>> mat;
    size_t nrows, ncols;
    float homex, homey, finesse, dist_sol, securite, nodataltitude;
    string output_path,topology;

    // Constructor
    Matrix(float _homex, float _homey, int _finesse, int _dist_sol, int _securite, int _nodataltitude, string _output_path, string _topology)
        : homex(_homex), homey(_homey), finesse(_finesse), dist_sol(_dist_sol), securite(_securite), 
         nodataltitude(_nodataltitude), output_path(_output_path), topology(_topology) {}

    // Method to read from file
    void readFile(){
    // cout <<"perso " << "read file" << endl;;
    ifstream file(topology);
    if (!file.is_open()) {
        cerr << "Compute could not open topology file." << endl;
        return 1;
    }

    string line1, line2, line3, line4, line5;

    // Read header
    getline(file, line1);
    size_t ncols = stoi(line1.substr(line1.find(' ') + 1));

    getline(file, line2);
    size_t nrows = stoi(line2.substr(line2.find(' ') + 1));

    getline(file, line3);
    float xllcorner = stoi(line3.substr(line3.find(' ') + 1));

    getline(file, line4);
    float yllcorner = stoi(line4.substr(line4.find(' ') + 1));

    getline(file, line5);
    float cellsize_m = stod(line5.substr(line5.find(' ') + 1));

    // Define subsection parameters
    size_t radius = static_cast<size_t>(nodataltitude*finesse/cellsize_m);  
    // cout<<"radius: "<<radius<<endl;

    size_t global_homei = nrows - 1 - static_cast<size_t>((homey - yllcorner) / cellsize_m);
    size_t global_homej = static_cast<size_t>((homex - xllcorner) / cellsize_m);
    // cout<<"global homei: "<<global_homei<<", global homej: "<<global_homej<<endl;

    size_t start_i = max(static_cast<int>(global_homei) - static_cast<int>(radius), 0);
    size_t end_i = min(global_homei + radius, nrows - 1);
    size_t start_j = max(static_cast<int>(global_homej) - static_cast<int>(radius), 0);
    size_t end_j = min(global_homej + radius, ncols - 1);

    size_t nrows_subsection = end_i - start_i + 1;
    size_t ncols_subsection = end_j - start_j + 1;

    size_t homei = global_homei - start_i;
    size_t homej = global_homej - start_j;
    // cout<<"homei: "<<homei<<", homej: "<<homej<<endl;

    cellsize_over_finesse = static_cast<float>(cellsize_m) / finesse;

    // vector<vector<Cell>> mat(nrows, vector<Cell>(ncols));
    vector<vector<Cell>> mat;
    mat.reserve(nrows_subsection);
    for (int i = 0; i < nrows_subsection; ++i) {
        mat.emplace_back(ncols_subsection);  // This is already optimal for your case
    }

    // Skip to the relevant rows
    for (int i = 0; i < start_i; ++i) {
        if(i>=nrows){break;}
        file.ignore(numeric_limits<streamsize>::max(), '\n');  // Skip lines before the subsection starts
    }
    // Process only the relevant rows and columns
    for (size_t i = 0; i < nrows_subsection; ++i) {
        if(i>=nrows){break;}
        string line;
        getline(file, line);
        istringstream iss_line(line);

        // Skip to the relevant columns
        for (int j = 0; j < start_j; ++j) {
            if(j>=ncols){break;}
            // cout<<j<<endl;
            iss_line.ignore(numeric_limits<streamsize>::max(), ' ');  // Skip to the next whitespace
        }

        // Read into the subsection
        for (size_t j = 0; j < ncols_subsection; ++j) {
            if(j>=ncols){break;}
            Cell* cell = &mat[i][j];
            iss_line >> cell->elevation;
            cell->i = i;
            cell->j = j;
            cell->altitude = nodataltitude;
        }
    }


    file.close();

    }

    // Getter for matrix dimensions
    size_t getNRows() const { return nrows; }
    size_t getNCols() const { return ncols; }

    // Getter for matrix data
    const vector<vector<Cell>>& getMatrix() const { return mat; }

    // Getter for other parameters
    float getXLLCorner() const { return xllcorner; }
    float getYLLCorner() const { return yllcorner; }
    float getCellSize() const { return cellsize_m; }
    float getCellSizeOverFinesse() const { return cellsize_over_finesse; }

    // Method to get a specific cell
    Cell& getCell(size_t i, size_t j) { return mat[i][j]; }
    const Cell& getCell(size_t i, size_t j) const { return mat[i][j]; }

    // Additional methods could be added here for operations on the matrix
};

#endif // MATRIX_H