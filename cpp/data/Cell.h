#ifndef CELL_H
#define CELL_H

#include <cstddef>
#include <vector>
#include <cmath>
#include "../io/Params.h"
using namespace std;

class Cell {
    public:
        float elevation;
        float altitude; // = nodataltitude, set after reading the file and getting nodataltitude;
        size_t oi =0;    
        size_t oj =0;    
        size_t i;
        size_t j;
        size_t weight =0;
        bool ground = false;
        bool mountain_pass = false;

        Cell(int elev = 0, size_t row = 0, size_t col = 0);

        void initialize(const Params& params);

        bool isInView(const size_t x2,const size_t y2, vector<vector<Cell>>& mat) const;

        float altitudeRequiseDepuis(const vector<vector<Cell>>& matrix, const int decalage_i, const int decalage_j,float cellsize_over_finesse) const;    

        bool calculate(const vector<vector<Cell>>& mat,const size_t oi, const size_t oj,const Params& params);    

};

#endif // CELL_H