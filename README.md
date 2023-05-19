# Raman OPU Analysis

An Operational phenotypic unit (OPU) analysis library for Raman single-cell
spectroscopy data

# Dependencies

This library requires `python>=3.6`; below packages are also required:

* numpy, scipy, scikit-learn
* matplotlib
* skfeature-chappers [1]

[1]: the original repo contains a bug in laplacian score; please use this
(https://github.com/lguangyu/scikit-feature.git) with my fixing commit instead.


# Installation

The installation is as easy as a single-line command:

```
pip install "opu-analysis-lib @ git+https://github.com/lguangyu/RamanSpecOPUAnalysis.git"
```

which will handle dependencies all together.


# Basic Usage

The library can be used both in CLI, Jupyter notebook or with another python
library. To use in CLI as a standalone script, run below command after a
successful installation:

```
opu_analysis -h
```

To use in Jupyter notebook/as a library to integrate with other analysis, simply
do:

```
from opu_analysis_lib import OPUAnalysis
```

The detailed analysis pipeline is stated in `doc/example.ipynb`.
