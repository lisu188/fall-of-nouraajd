/*
 * MIT License
 *
 * Copyright (c) 2019 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#include "vutil.h"

namespace vstd {
    template<typename T=void>
    class neuro {
        std::vector<int> _str;
        std::vector<int> _dim;
        double _alfa, _beta, _eta;
        int _nw;
        std::vector<std::pair<double *, double *>> teachers;
        std::vector<std::pair<double *, double *>> tests;
        double ***_neuro, ***_prev, ***_diff;
        double **_o, **_e;

        double fcn(double x, double beta) {
            return 1.0 / (1.0 + std::exp(-beta * x));
        }

        double dfcn(double x) {
            return (1.0 - x) * x;
        }

        void o(double *t) {
            for (int j = 0; j < _str[0]; j++) {
                _o[0][j] = t[j];
            }
            for (int i = 1; i < _nw; i++) {
                for (int j = 0; j < _str[i]; j++) {
                    _o[i][j] = 0;
                    for (int k = 0; k < _str[i - 1]; k++) {
                        _o[i][j] += _o[i - 1][k] * _neuro[i - 1][j][k];
                    }
                    _o[i][j] = fcn(_o[i][j], _beta);
                }
            }
        }

        void e(double *in, double *out) {
            o(in);
            for (int i = 0; i < _str[_nw - 1]; i++) {
                _e[_nw - 2][i] = dfcn(out[i] - _o[_nw - 1][i]);
            }

            for (int j = 3; _nw - j >= 0; j++) {
                for (int k = 0; k < _str[_nw - j + 1]; k++) {
                    _e[_nw - j][k] = 0;
                }
                for (int k = 0; k < _str[_nw - j + 1]; k++) {
                    for (int l = 0; l < _str[_nw - j + 2]; l++) {
                        _e[_nw - j][k] += _e[_nw - j + 1][l] * _neuro[_nw - j + 1][l][k];
                    }
                }
                for (int k = 0; k < _str[_nw - j + 1]; k++) {
                    _e[_nw - j][k] *= dfcn(_o[_nw - j + 1][k]);
                }
            }
        }

    public:
        void add_teacher(std::vector<double> in, std::vector<double> out) {
            teachers.push_back(std::make_pair(vstd::as_array(in), vstd::as_array(out)));
        }

        void add_test(std::vector<double> in, std::vector<double> out) {
            tests.push_back(std::make_pair(vstd::as_array(in), vstd::as_array(out)));
        }

        int teach(double erms, int step = 1) {
            int i = 0;
            while (this->erms() > erms) {
                teach(step);
                i += step;
            }
            return i;
        }

        void teach(int ite) {
            if (teachers.size() != 0) {
                while (ite-- > 0) {
                    for (int i = 0; i < _nw - 1; i++) {
                        for (int j = 0; j < _str[i + 1]; j++) {
                            for (int k = 0; k < _str[i]; k++) {
                                _diff[i][j][k] = _neuro[i][j][k] - _prev[i][j][k];
                                _prev[i][j][k] = _neuro[i][j][k];
                            }
                        }
                    }

                    std::shuffle(teachers.begin(), teachers.end(), vstd::rng());

                    for (auto t:teachers) {
                        o(t.first);
                        e(t.first, t.second);

                        for (int j = 0; j < _nw - 1; j++) {
                            for (int k = 0; k < _str[j + 1]; k++) {
                                for (int l = 0; l < _str[j]; l++) {
                                    _neuro[j][k][l] += (_eta * _e[j][k] * _o[j][l]) / teachers.size();
                                }
                            }
                        }
                    }

                    for (int i = 0; i < _nw - 1; i++) {
                        for (int j = 0; j < _str[i + 1]; j++) {
                            for (int k = 0; k < _str[i]; k++) {
                                _neuro[i][j][k] += _alfa * _diff[i][j][k];
                            }
                        }
                    }
                }
            }
        }

        double erms() {
            double erms = 0;
            double tmp;
            double *out_t, *out_n;
            for (auto teacher : teachers) {
                tmp = 0;
                out_t = teacher.second;
                o(teacher.first);
                for (int k = 0; k < _str[_nw - 1]; k++) {
                    tmp += std::pow(out_t[k] - _o[_nw - 1][k], 2);
                }
                erms += std::sqrt(tmp / _str[_nw - 1]);
            }
            return erms / teachers.size();
        }

        double test() {
            double erms = 0;
            double tmp;
            double *out_t, *out_n;
            for (auto teacher : tests) {
                tmp = 0;
                out_t = teacher.second;
                o(teacher.first);
                for (int k = 0; k < _str[_nw - 1]; k++) {
                    tmp += std::pow(out_t[k] - _o[_nw - 1][k], 2);
                }
                erms += std::sqrt(tmp / _str[_nw - 1]);
            }
            return erms / teachers.size();
        }

        neuro(std::vector<int> str,
              double alfa,
              double beta,
              double eta
        ) :

                _str(str), _alfa(alfa),
                _beta(beta),
                _eta(eta),
                _nw((unsigned int) str.size()) {
            _neuro = vstd::allocate<double **>(_nw - 1);
            _prev = vstd::allocate<double **>(_nw - 1);
            _diff = vstd::allocate<double **>(_nw - 1);
            for (int i = 0; i < _nw - 1; i++) {
                _neuro[i] = vstd::allocate<double *>(_str[i + 1]);
                _prev[i] = vstd::allocate<double *>(_str[i + 1]);
                _diff[i] = vstd::allocate<double *>(_str[i + 1]);
                for (int j = 0; j < _str[i + 1]; j++) {
                    _neuro[i][j] = vstd::allocate<double>(_str[i]);
                    _prev[i][j] = vstd::allocate<double>(_str[i]);
                    _diff[i][j] = vstd::allocate<double>(_str[i]);
                    for (int k = 0; k < _str[i]; k++) {
                        _diff[i][j][k] = _neuro[i][j][k] = _prev[i][j][k] = vstd::rand();
                    }
                }
            }

            _e = vstd::allocate<double *>(_nw - 1);
            for (int i = 0; i < _nw - 1; i++) {
                _e[i] = vstd::allocate<double>(_str[i + 1]);
            }

            _o = vstd::allocate<double *>(_nw);
            for (int i = 0; i < _nw; i++) {
                _o[i] = vstd::allocate<double>(_str[i]);
            }
        };


        ~neuro() {
            for (int i = 0; i < _nw - 1; i++) {
                for (int j = 0; j < _str[i + 1]; j++) {
                    vstd::deallocate(_neuro[i][j], _str[i]);
                    vstd::deallocate(_prev[i][j], _str[i]);
                    vstd::deallocate(_diff[i][j], _str[i]);
                }
                vstd::deallocate(_neuro[i], _str[i + 1]);
                vstd::deallocate(_prev[i], _str[i + 1]);
                vstd::deallocate(_diff[i], _str[i + 1]);
            }
            vstd::deallocate(_neuro, _nw - 1);
            vstd::deallocate(_prev, _nw - 1);
            vstd::deallocate(_diff, _nw - 1);

            for (int i = 0; i < _nw - 1; i++) {
                vstd::deallocate(_e[i], _str[i + 1]);
            }
            vstd::deallocate(_e, _nw - 1);

            for (int i = 0; i < _nw; i++) {
                vstd::deallocate(_o[i], _str[i]);
            }
            vstd::deallocate(_o, _nw - 1);

            for (auto teacher:teachers) {
                vstd::deallocate(teacher.first, _str[0]);
                vstd::deallocate(teacher.second, _str[_str.size() - 1]);
            }

            for (auto test:tests) {
                vstd::deallocate(test.first, _str[0]);
                vstd::deallocate(test.second, _str[_str.size() - 1]);
            }
        }
    };
}
