# Raman OPU Analysis

An Operational phenotypic unit (OPU) analysis library for Raman single-cell
spectroscopy data

# Dependencies

This library requires `python>=3.6`; below packages are also required:

* numpy, scipy, scikit-learn
* matplotlib
* skfeature-chappers [1]

[1]: the original repo contains a bug laplacian score; please use this version
(https://github.com/lguangyu/scikit-feature.git) with my fixing commit instead.


# Installation

The installation is as easy as a single-line command:

```
pip install "opu-analysis-lib @ git+https://github.com/lguangyu/RamanSpecOPUAnalysis.git"
```

which will handle all the dependencies all together.
