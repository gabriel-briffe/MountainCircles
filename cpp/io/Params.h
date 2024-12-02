#ifndef PARAMS_H
#define PARAMS_H

#include <cstddef>
#include <string>
using namespace std;

class Params {
    public:
        size_t global_ncols,global_nrows;
        float homex, homey, finesse, distSol, securite, 
            nodataltitude,cellsize_m,cellsize_over_finesse, 
            xllcorner, yllcorner;
        string output_path, topology, exportPasses;

        Params(int argc, char* argv[]);
};

#endif // PARAMS_H