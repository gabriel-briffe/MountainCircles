#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip>
#include "src/cell.h"
#include "src/matrix.h"
#include "src/params.h"
using namespace std;


int main(int argc, char* argv[]) {

    try {
        Params params(argc, argv);
        Matrix M(params);

        M.mat[M.homei][M.homej].initialize(params);

        M.addGroundClearance(params);

        M.calculate_safety_altitude(params);

        M.update_altitude_for_ground_cells(0);  //set ground altitude to 0 - useful for recombining all tiles

        M.write_output(params, params.output_path + "/output_sub.asc", false);  //ground altitude set to 0 - useful for recombining all tiles
        M.write_output(params, params.output_path + "/local.asc", true);    //ground altitude set to nodata - ground transparent


        bool shouldExportPasses = (params.exportPasses == "true" || params.exportPasses == "1" || atoi(params.exportPasses.c_str()) != 0);
        
        if (shouldExportPasses){
            M.detect_passes(params);
            M.weight_passes(params);
            M.write_mountain_passes(params,params.output_path + "/mountain_passes.csv");
        }


        // cout << "calcul "<<params.output_path<<" fini"<<endl;

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}