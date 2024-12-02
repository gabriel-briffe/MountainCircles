#ifndef MATRIX_H
#define MATRIX_H

#include "../io/Params.h"
#include "Cell.h"
#include <cstddef>
#include <tuple>
#include <vector>
using namespace std;

class Matrix {
public:
    vector<vector<Cell>> mat;
    size_t nrows, ncols, homei, homej,start_i,end_i,start_j,end_j;

    // Constructor
    Matrix(Params& params);

    // Method to read from file
    void readFile(Params& params);

    void calculate_safety_altitude(const Params& params);

    //peut être pas une bonne idée d'avoir une fonction inline aussi grosse
    inline vector<tuple<size_t, size_t, size_t, size_t>> neighbours_with_different_origin_for_stack(const size_t i, const size_t j) const {
        vector<tuple<size_t, size_t, size_t, size_t>> neighbours;
        const Cell* cellPtr= &this->mat[i][j];
        const size_t oi = cellPtr->oi;
        const size_t oj = cellPtr->oj;

        // Define the 4 directions for neighbors (excluding diagonals)
        const vector<pair<int, int>> directions = {
            {-1, 0}, {1, 0}, {0, -1}, {0, 1} // Up, Down, Left, Right
        };

        for (const auto& dir : directions) {
            size_t ni = i + dir.first;
            size_t nj = j + dir.second;

            if (isInsideMatrix(ni,nj)){
                if (this->mat[ni][nj].oi != oi || this->mat[ni][nj].oj != oj) {
                    neighbours.emplace_back(ni, nj, i, j);
                }
            }
        }

        return neighbours;
    }

    bool isInsideMatrix(const size_t i, const size_t j) const;

    void update_altitude_for_ground_cells(const float altivisu);

    void addGroundClearance(const Params& params);

    void write_output(const Params& params, const string& destinationFile, const bool nozero) const;

    void detect_passes(Params& params);

    void weight_passes(Params& params);

    void update_cell_weight(Cell& cell, Params& params, size_t max_depth = 1000);

    void write_mountain_passes(const Params& params, const string& destinationFile) const;

};

#endif // MATRIX_H