#include "Cell.h"


Cell::Cell(int elev, size_t row, size_t col) : elevation(elev), i(row), j(col) {}

void Cell::initialize(const Params& params){
    this->altitude=this->elevation+params.securite;
    this->oi = this->i;
    this->oj = this->j;
}

bool Cell::isInView(const size_t x2,const size_t y2, vector<vector<Cell>>& mat) const {
    size_t x1 = this->i;
    size_t y1 = this->j;
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

float Cell::altitudeRequiseDepuis(const vector<vector<Cell>>& matrix, const int decalage_i, const int decalage_j,float cellsize_over_finesse) const {
    return hypot(decalage_i,decalage_j)*cellsize_over_finesse+matrix[this->i][this->j].altitude;
}     

bool Cell::calculate(const vector<vector<Cell>>& mat,const size_t oi, const size_t oj,const Params& params) {
    float requiredAltitude = mat[oi][oj].altitudeRequiseDepuis(mat,this->i-oi,this->j-oj,params.cellsize_over_finesse);
    float altitude = this->altitude;
    if (this->oi!=0 &&  requiredAltitude >= altitude){
        return false;
    }
    if (requiredAltitude <= this->elevation) {
        this->altitude = this->elevation;
        this->oi=i; this->oj=j;
        this->ground=true;
        // return true;
    } else {
        this->altitude = requiredAltitude;
        this->oi=oi; this->oj=oj;
        // return true;
    }
    if (requiredAltitude>=params.nodataltitude) {
        return false;
    }
    return true;
}      