#include "Matrix.h"

#include "../io/Params.h"
#include "Cell.h"
#include <cstddef>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <tuple>
#include <vector>
using namespace std;


// Constructor
Matrix::Matrix(Params& params) {
    readFile(params);
}

// Method to read from file
void Matrix::readFile(Params& params) {
    ifstream file(params.topology);
    if (!file.is_open()) {
        throw runtime_error("Compute could not open topology file.");
    }

    string line1, line2, line3, line4, line5;

    // Read header
    try {
        if (!getline(file, line1)) throw runtime_error("Failed to read ncols from file.");
        params.global_ncols = stoi(line1.substr(line1.find(' ') + 1));

        if (!getline(file, line2)) throw runtime_error("Failed to read nrows from file.");
        params.global_nrows = stoi(line2.substr(line2.find(' ') + 1));

        if (!getline(file, line3)) throw runtime_error("Failed to read xllcorner from file.");
        params.xllcorner = stof(line3.substr(line3.find(' ') + 1));

        if (!getline(file, line4)) throw runtime_error("Failed to read yllcorner from file.");
        params.yllcorner = stof(line4.substr(line4.find(' ') + 1));

        if (!getline(file, line5)) throw runtime_error("Failed to read cellsize from file.");
        params.cellsize_m = stod(line5.substr(line5.find(' ') + 1));

        params.cellsize_over_finesse = params.cellsize_m / params.finesse;

        // Define subsection parameters
        size_t radius = static_cast<size_t>(params.nodataltitude / params.cellsize_over_finesse);

        size_t global_homei = params.global_nrows - 1 - static_cast<size_t>((params.homey - params.yllcorner) / params.cellsize_m);
        size_t global_homej = static_cast<size_t>((params.homex - params.xllcorner) / params.cellsize_m);

        this->start_i = max(static_cast<int>(global_homei) - static_cast<int>(radius), 0);
        this->end_i = min(global_homei + radius, params.global_nrows - 1);
        this->start_j = max(static_cast<int>(global_homej) - static_cast<int>(radius), 0);
        this->end_j = min(global_homej + radius, params.global_ncols - 1);

        this->nrows = end_i - start_i + 1;
        this->ncols = end_j - start_j + 1;

        this->homei = global_homei - start_i;
        this->homej = global_homej - start_j;

        this->mat.resize(this->nrows, vector<Cell>(this->ncols));

        // Skip to the relevant rows
        for (int i = 0; i < start_i; ++i) {
            file.ignore(numeric_limits<streamsize>::max(), '\n');
        }

        // Process only the relevant rows and columns
        for (size_t i = 0; i < this->nrows; ++i) {
            if (!getline(file, line1)) {
                throw runtime_error("Unexpected end of file or read error when processing matrix.");
            }
            istringstream iss_line(line1);

            // Skip to the relevant columns
            for (int j = 0; j < start_j; ++j) {
                iss_line.ignore(numeric_limits<streamsize>::max(), ' ');
            }

            // Read into the subsection
            for (size_t j = 0; j < this->ncols; ++j) {
                Cell* cell = &this->mat[i][j];
                if (!(iss_line >> cell->elevation)) {
                    throw runtime_error("Failed to read elevation data for cell at position " + to_string(i) + ", " + to_string(j));
                }
                cell->i = i;
                cell->j = j;
                cell->altitude = params.nodataltitude;
            }
        }
    } catch (const exception& e) {
        file.close();
        throw; // Re-throw the caught exception after closing the file
    }
}

void Matrix::calculate_safety_altitude(const Params& params) {
    deque<tuple<size_t, size_t, size_t, size_t>> stack;
        
    vector<tuple<size_t, size_t, size_t, size_t>> initial_stack = neighbours_with_different_origin_for_stack(this->homei, this->homej);
    stack.insert(stack.end(), initial_stack.begin(), initial_stack.end());

    while (!stack.empty()) {
        
        size_t i, j, parenti, parentj;
        tie(i, j, parenti, parentj) = stack.front();
        stack.pop_front();
        
        Cell& cell = this->mat[i][j];
        Cell& parent = this->mat[parenti][parentj];

        if(parent.oi==cell.oi && parent.oj==cell.oj){continue;}
        if(cell.ground){continue;}


        size_t oi_elected,oj_elected;
        if( cell.isInView(parent.oi,parent.oj,this->mat)){
            oi_elected=parent.oi;
            oj_elected=parent.oj;
        } else {
            oi_elected=parent.i;
            oj_elected=parent.j;
        }

        if(oi_elected==cell.oi && oj_elected==cell.oj){continue;} 
        bool updated;
        updated = cell.calculate(this->mat, oi_elected, oj_elected, params);

        // add nb cells with different origins to stack
        if (updated){
            auto new_neighbours = neighbours_with_different_origin_for_stack(i, j);
            stack.insert(stack.end(), new_neighbours.begin(), new_neighbours.end());
            // if (parent.ground && !cell.ground){
            //     cell.mountain_pass = true;
            // } else {
            //     cell.mountain_pass = false;
            // }
        }
    }
}

bool Matrix::isInsideMatrix(const size_t i, const size_t j) const {
return i >= 0 && i < this->nrows && j >= 0 && j < this->ncols;
}

void Matrix::update_altitude_for_ground_cells(const float altivisu) {
    for (auto& row : this->mat) {
        for (auto& cell : row) {
            if (cell.ground) {
                cell.altitude = altivisu;
            }
        }
    }
}

void Matrix::addGroundClearance(const Params& params){
    for (size_t i = 0; i < this->nrows; ++i) {
        for (size_t j = 0; j < this->ncols; ++j) {
            this->mat[i][j].elevation += params.distSol;
        }
    }
}

void Matrix::write_output(const Params& params, const string& destinationFile, const bool nozero) const {
    ofstream outputFile(destinationFile);
    
    if (outputFile.is_open()) {
        // Write the header
        outputFile << "ncols " << this->ncols << "\n"
                << "nrows " << this->nrows << "\n"
                << "xllcorner " << (params.xllcorner + this->start_j * params.cellsize_m) << "\n"  // adjust xllcorner
                << "yllcorner " << (params.yllcorner + (params.global_nrows - 1 - this->end_i) * params.cellsize_m) << "\n"  // adjust yllcorner
                << "cellsize " << params.cellsize_m << "\n"  // Keep the original cellsize
                << "NODATA_value " << params.nodataltitude << "\n";

        // Write the data
        if(nozero){
            for (size_t i = 0; i < this->nrows; ++i) {
                for (size_t j = 0; j < this->ncols; ++j) {
                    if (this->mat[i][j].altitude == 0) {
                        outputFile << params.nodataltitude;
                    } else {
                        outputFile << this->mat[i][j].altitude;
                    }
                    if (j < this->ncols - 1) outputFile << " "; // Add space between values except at the end of the row
                }
                outputFile << "\n"; // New line after each row
            }
        } else {
            for (size_t i = 0; i < this->nrows; ++i) {
                for (size_t j = 0; j < this->ncols; ++j) {
                    outputFile << this->mat[i][j].altitude;
                    if (j < this->ncols - 1) outputFile << " "; // Add space between values except at the end of the row
                }
                outputFile << "\n"; // New line after each row
            }

        }

        outputFile.close();
    } else {
        cerr << "Unable to open file " << destinationFile << " for writing." << endl;
    }
}

void Matrix::detect_passes(Params& params) {
    for (size_t i = 0; i < this->nrows; ++i) {
        for (size_t j = 0; j < this->ncols; ++j) {
            Cell& cell = this->mat[i][j];
            Cell& origin = this->mat[cell.oi][cell.oj];
            if (origin.ground && !cell.ground){
                cell.mountain_pass = true;
            } else {
                cell.mountain_pass = false;
            }
        }

    }
}


void Matrix::weight_passes(Params& params) {
    for (size_t i = 0; i < this->nrows; ++i) {
        for (size_t j = 0; j < this->ncols; ++j) {
            Cell& cell = this->mat[i][j];
            update_cell_weight(cell,params);
        }

    }
}


void Matrix::update_cell_weight(Cell& cell, Params& params, size_t max_depth) {
    if (max_depth == 0) {
        throw std::runtime_error("Maximum recursion depth reached.");
    }

    Cell& origin = this->mat[cell.oi][cell.oj];
    origin.weight++;

    // Check if we should continue recursion
    if (!origin.ground && (origin.i!=cell.i || origin.j!=cell.j)) { 
        update_cell_weight(origin, params, max_depth - 1);
    }
}

void Matrix::write_mountain_passes(const Params& params, const string& destinationFile) const {
    ofstream outputFile(destinationFile);
    
    if (outputFile.is_open()) {
        outputFile <<"name,x,y,weight"<<endl;
        // Write the data
        for (size_t i = 0; i < this->nrows; ++i) {
            for (size_t j = 0; j < this->ncols; ++j) {
                const Cell& cell = this->mat[i][j];
                const Cell& origine = this->mat[cell.oi][cell.oj];
                const Cell& oorigine = this->mat[origine.oi][origine.oj];
                if (cell.mountain_pass && cell.weight>100 && oorigine.ground ){
                    outputFile <<"pass,"<< params.xllcorner + (this->start_j+cell.j) * params.cellsize_m <<","
                    << params.yllcorner + (params.global_nrows - 1 -this->start_i - cell.i) * params.cellsize_m <<","
                    << cell.weight <<endl;

                }
            }

        }

        outputFile.close();
    } else {
        cerr << "Unable to open file " << destinationFile << " for writing." << endl;
    }
}