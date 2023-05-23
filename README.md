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

## Command-line

The library can be used both in CLI, Jupyter notebook or with another python
library. The example below shows the usage in CLI as a standalone script:

```bash
cd doc # this is where the example is
opu_analysis example.json \
	-b 5.0 -L 400 -H 1800 -N l2 \
	--metric cosine \
	--cutoff-threshold 0.7 \
	--opu-min-size 0.05 \
	--opu-labels example.json.opu_labels.txt \
	--opu-collection-prefix example.json.opu_collection \
	--opu-hca-plot example.json.hca.png \
	--abund-stackbar-plot example.json.opu_abund.png \
	--abund-biplot example.json.opu_pca.png \
	--feature-rank-method fisher_score \
	--feature-rank-table example.json.opu_feature_rank.tsv \
	--feature-rank-plot example.json.opu_feature_rank.png
```

## Jupyter notebook

To use in Jupyter notebook/as a library to integrate with other analysis, simply
do:

```
from opu_analysis_lib import OPUAnalysis
```

The detailed analysis pipeline is stated in `doc/example.ipynb`.
