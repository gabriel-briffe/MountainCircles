#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <tuple>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <queue>
#include <unordered_set>
#include <utility>
using namespace std;

// const string homename = "albertville";
// const float homex = 3166087;
// const float homey = 1775691;

int finesse;
int distSol;
int securite;
int nodataltitude ;
float cellsize_m;
float cellsize_over_finesse;

struct Cell {
    float elevation;
    float altitude = nodataltitude;
    size_t oi =0;    
    size_t oj =0;    
    size_t i;
    size_t j;
    bool ground = false;
    // Constructor to initialize origin
    Cell(int elev = 0, size_t row = 0, size_t col = 0) : elevation(elev), i(row), j(col) {}
};

float altitudeRequiseDepuis(vector<vector<Cell>>& matrix, const size_t i, const size_t j, const int decalage_i, const int decalage_j){
    return hypot(decalage_i,decalage_j)*cellsize_over_finesse+matrix[i][j].altitude;
}

bool isInsideMatrix(const size_t nrows, const size_t ncols, const size_t i, const size_t j) {
    return i >= 0 && i < nrows && j >= 0 && j < ncols;
}

bool calculate(vector<vector<Cell>>& mat ,size_t i,size_t j,size_t oi,size_t oj) {
    float requiredAltitude = altitudeRequiseDepuis(mat,oi,oj,i-oi,j-oj);
    Cell* cellPtr= &mat[i][j];
    float altitude = cellPtr->altitude;
    if (cellPtr->oi!=0 &&  requiredAltitude >= altitude){
        // cout <<"perso "<<"avoid worsening or equal update"<<endl;
        return false;
    }
    if (requiredAltitude <= cellPtr->elevation) {
        cellPtr->altitude = cellPtr->elevation;
        cellPtr->oi=i; cellPtr->oj=j;
        cellPtr->ground=true;
        // return true;
    } else {
        cellPtr->altitude = requiredAltitude;
        cellPtr->oi=oi; cellPtr->oj=oj;
        // return true;
    }
    if (requiredAltitude>=nodataltitude) {
        return false;
    }
    return true;
}


vector<tuple<size_t, size_t, size_t, size_t>> neighbours_with_different_origin_for_stack(size_t i, size_t j, vector<vector<Cell>>& mat,const size_t nrows,const size_t ncols) {
    vector<tuple<size_t, size_t, size_t, size_t>> neighbours;
    const Cell* cellPtr= &mat[i][j];
    const size_t oi = cellPtr->oi;
    const size_t oj = cellPtr->oj;

    // Define the 4 directions for neighbors (excluding diagonals)
    const vector<pair<int, int>> directions = {
        {-1, 0}, {1, 0}, {0, -1}, {0, 1} // Up, Down, Left, Right
    };

    for (const auto& dir : directions) {
        size_t ni = i + dir.first;
        size_t nj = j + dir.second;

        if (isInsideMatrix(nrows,ncols,ni,nj)){
            if (mat[ni][nj].oi != oi || mat[ni][nj].oj != oj) {
                neighbours.emplace_back(ni, nj, i, j);
            }
        }
    }

    return neighbours;
}


bool bresenham_like_line_check_passes(size_t x1, size_t y1, size_t x2, size_t y2, vector<vector<Cell>>& mat) {
    // Helper function to test if the origin matches
    auto test_origin = [&](size_t x, size_t y) -> bool { //------------------------peut etre besoin de pas le mettre----------------
        return !mat[x][y].ground;
    };

    if (x1 == x2 && y1 == y2) {
        return true;
    }
    if (abs(static_cast<int>(x1) - static_cast<int>(x2)) <= 1 && abs(static_cast<int>(y1) - static_cast<int>(y2)) <= 1) {
        return true;
    }

    int xstep = (x2 > x1) ? 1 : -1;
    int ystep = (y2 > y1) ? 1 : -1;

    int dx = abs(static_cast<int>(x2) - static_cast<int>(x1));
    int dy = abs(static_cast<int>(y2) - static_cast<int>(y1));

    int ddy = dy * 2;
    int ddx = dx * 2;

    int error = dx;
    int errorprev = error;

    if (dx >= dy) {
        for (size_t i = 0; i < dx; ++i) {
            x1 += xstep;
            error += ddy;
            if (error > ddx) {
                y1 += ystep;
                error -= ddx;
                if (error + errorprev < ddx) {
                    if (mat[x1][y1 - ystep].ground) {
                        return false;
                    }
                } else if (error + errorprev > ddx) {
                    if (mat[x1 - xstep][y1].ground) {
                        return false;
                    }
                }
            }
            if (mat[x1] [y1].ground) {
                return false;
            }
            errorprev = error;
        }
    } else {
        for (size_t i = 0; i < dy; ++i) {
            y1 += ystep;
            error += ddx;
            if (error > ddy) {
                x1 += xstep;
                error -= ddy;
                if (error + errorprev < ddy) {
                    if (mat[x1 - xstep][ y1].ground) {
                        return false;
                    }
                } else if (error + errorprev > ddy) {
                    if (mat[x1] [y1 - ystep].ground) {
                        return false;
                    }
                }
            }
            if (mat[x1][ y1].ground) {
                return false;
            }
            errorprev = error;
        }
    }

    return true;
}

void update_altitude_for_ground_cells(vector<vector<Cell>>& mat,float altivisu) {
    for (auto& row : mat) {
        for (auto& cell : row) {
            if (cell.ground) {
                cell.altitude = altivisu;
            }
        }
    }
}


/*----------------------------------------------------------------------------------------------------------------------------------------------------------------------*/
/*----------------------------------------------------------------------------------------------------------------------------------------------------------------------*/
/*----------------------------------------------------------------------------------------------------------------------------------------------------------------------*/
/*----------------------------------------------------------------------------------------------------------------------------------------------------------------------*/

void calculate_safety_altitude(vector<vector<Cell>>& mat, size_t homei,size_t homej,size_t nrows,size_t ncols) {
    deque<tuple<size_t, size_t, size_t, size_t>> stack;
        
    vector<tuple<size_t, size_t, size_t, size_t>> initial_stack = neighbours_with_different_origin_for_stack(homei, homej, mat, nrows, ncols);
    stack.insert(stack.end(), initial_stack.begin(), initial_stack.end());

    while (!stack.empty()) {
        
        size_t i, j, parenti, parentj;
        tie(i, j, parenti, parentj) = stack.front();
        stack.pop_front();
        
        Cell& cell = mat[i][j];
        Cell& parent = mat[parenti][parentj];

        if(parent.oi==cell.oi && parent.oj==cell.oj){/* cout<<"perso parent origin identique --> abort"<<endl; */ continue; }
        // if(parent.i==cell.oi && parent.j==cell.oj){cout<<"perso parent deja l'origine"<<endl; }
        if(cell.ground){continue;}


        size_t oi_elected,oj_elected;
        if( bresenham_like_line_check_passes(cell.i,cell.j,parent.oi,parent.oj,mat)){
            oi_elected=parent.oi;
            oj_elected=parent.oj;
        } else {
            oi_elected=parent.i;
            oj_elected=parent.j;
        }

        if(oi_elected==cell.oi && oj_elected==cell.oj){/* cout<<"perso test2"<<endl; */ continue;}  //cas où le test de la cellule déja calculée s'est fait, avec plusieurs origines autours, mais qui ne change rien
        bool updated;
        updated = calculate(mat, i, j, oi_elected, oj_elected);

        // if(cell.ground){continue;}
        // add nb cells with different origins to stack
        if (updated){
            // cout << "perso been updated "  << endl;
            auto new_neighbours = neighbours_with_different_origin_for_stack(i, j, mat,nrows,ncols);
            stack.insert(stack.end(), new_neighbours.begin(), new_neighbours.end());
        }
    }
}





int main(int argc, char* argv[]) {

// const float homex = 3166087;
// const float homey = 1775691;
// ./compute 3166087 1775691 20 200 250 1000 .
    float homex = atoi(argv[1]);
    float homey = atoi(argv[2]);
    finesse = atoi(argv[3]);
    distSol = atoi(argv[4]);
    securite = atoi(argv[5]);
    nodataltitude = atoi(argv[6]);
    string output_path = argv[7];
    string topology = argv[8];
    // float homex = 3166087;
    // float homey = 1775691;
    // finesse = 20;
    // distSol = 200;
    // securite = 250;
    // nodataltitude = 2000;
    // string output_path = ".";
    // cout<<homex<<" "<<homey<<" "<<finesse<<" "<<distSol<<" "<<securite<<" "<<nodataltitude<<endl;


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
    // size_t radius = 50;  // Example radius, adjust as needed
    size_t radius = static_cast<size_t>(nodataltitude*finesse/cellsize_m);  // Example radius, adjust as needed
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

    // size_t nrows_subsection = 1+min(radius,nrows-1-global_homei)+min(radius,global_homei);
    // size_t ncols_subsection = 1+min(radius,ncols-1-global_homej)+min(radius,global_homej);  
    // cout<<"nrowsub: "<<nrows_subsection<<", ncolsub: "<<ncols_subsection<<endl;  
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
            iss_line >> mat[i][j].elevation;
            mat[i][j].i = i;
            mat[i][j].j = j;
        }
    }


    file.close();

    // cout <<"perso " << "initialize" << endl;


    Cell* home = &mat[homei][homej];
    home->altitude = home->elevation + securite;
    home->oi = homei;
    home->oj = homej;
    size_t oi,oj;
    oi=home->oi;
    oj=home->oj;
    // cout <<"perso "<<"homei: "<<homei<<", homej: "<<homej<<", oi: "<< oi <<", oj: "<< oj <<" "<<output_path<< endl;


    for (size_t i = 0; i < nrows_subsection; ++i) {
        for (size_t j = 0; j < ncols_subsection; ++j) {
            mat[i][j].elevation += distSol;
        }
    }

    // cout <<"perso " << "calculate..." << endl;
    // auto start = chrono::high_resolution_clock::now();
    calculate_safety_altitude(mat,homei,homej,nrows_subsection,ncols_subsection);
    // auto end = chrono::high_resolution_clock::now();

    update_altitude_for_ground_cells(mat,0);

    // home->altitude = 3000;

    // cout <<"perso " << "write" << endl;
    ofstream outputFile(output_path+"/output_sub.asc");
    ofstream localFile(output_path+"/local.asc");

    if (outputFile.is_open()) {
    outputFile << "ncols " << ncols_subsection << "\n"
               << "nrows " << nrows_subsection << "\n"
               << "xllcorner " << (xllcorner + start_j * cellsize_m) << "\n"  // adjust xllcorner
               << "yllcorner " << (yllcorner + (nrows - 1 - end_i) * cellsize_m) << "\n"  // adjust yllcorner
               << line5 << "\n"  // Keep the original cellsize
               << "NODATA_value " << nodataltitude << "\n";

    // Write the data
    for (size_t i = 0; i < nrows_subsection; ++i) {
        for (size_t j = 0; j < ncols_subsection; ++j) {
            outputFile << mat[i][j].altitude;
            if (j < ncols_subsection - 1) outputFile << " "; // Add space between values except at the end of the row
        }
        outputFile << "\n"; // New line after each row
    }

        outputFile.close();
    } else {
        cerr << "Unable to open file for writing." << endl;
    }


    if (localFile.is_open()) {
    localFile << "ncols " << ncols_subsection << "\n"
               << "nrows " << nrows_subsection << "\n"
               << "xllcorner " << (xllcorner + start_j * cellsize_m) << "\n"  // adjust xllcorner
               << "yllcorner " << (yllcorner + (nrows - 1 - end_i) * cellsize_m) << "\n"  // adjust yllcorner
               << line5 << "\n"  // Keep the original cellsize
               << "NODATA_value " << nodataltitude << "\n";

    // Write the data
    for (size_t i = 0; i < nrows_subsection; ++i) {
        for (size_t j = 0; j < ncols_subsection; ++j) {
            if (mat[i][j].altitude == 0) {
                localFile << nodataltitude;
            } else {
                localFile << mat[i][j].altitude;
            }            
            if (j < ncols_subsection - 1) localFile << " "; // Add space between values except at the end of the row
        }
        localFile << "\n"; // New line after each row
    }

        localFile.close();
    } else {
        cerr << "Unable to open file for writing." << endl;
    }

    cout << "calcul "<<output_path<<" fini"<<endl;
    // Calculate the duration
    // chrono::duration<double, milli> elapsed = end - start;

    // Output the time taken
    // cout << "perso      Time elapsed: " << elapsed.count()/1000 << " s" << endl;
    // cout<< endl; cout<<endl;

    return 0;
}