# Raman OPU Analysis

An Operational phenotypic unit (OPU) analysis library for Raman single-cell
spectroscopy data

# Dependencies

This library requires `python>=3.6`; below packages are also required:

* numpy, scipy, scikit-learn
* matplotlib
* mpllayout
* skfeature [1]

[1]: the original repo contains a bug in laplacian score; in the installation
below the actual package used (skfeature-gli) can be found at
(https://github.com/lguangyu/scikit-feature.git)


# Installation

The installation is as easy as a single-line command:

```
pip install raman-opu-analysis
```

# Synopsis and Basic Command-line Usage

This package provide main command-line scripts:

* `opu_analysis`: the main analysis script
* `opu_dataset_manip`: a supporting script to manipulate and visualize dataset files

## OPU Analysis

The library can be used both in CLI, Jupyter notebook or with another python library. The example below shows the usage in CLI as a standalone script:

If you have already prepared 

### Parepare the Dataset Config File

A json config file need to be prepared before using the `opu_analysis` script. The config is a list of biosample configs, in the following structure:

```json
[
	{
		# biosample-1 configs
	},
	{
		# biosample-2 configs
	},
	... # repeat to add more
]
```

Each of the biosample config contains 3 keys-value paris:

* `name`: name of the biosample, will be shown in outputs
* `color`: color of the biosample, currently only used in the HCA plot, in the standard HTML format (`#RRGGBB`)
* `file`: the tabular data file(s) belong to the biosample, it can be a string (as the path to the data file) or a list (paths to the data files).

An example is:

```json
{
	"name": "biosample-1",
	"color": "#0000ff",
	"file": "biosample-1.data.tsv"
}
```

Another example with `file` being a list:

```json
{
	"name": "biosample-2",
	"color": "#0000ff",
	"file": [
		"biosample-2.data_1.tsv",
		"biosample-2.data_2.tsv"
	]
}
```

All files in that list will be combined under the related biosample, and will not be distinguished unless investigating the spectra names in outputs.

An functional example of such config json can be found in `doc/example.json`.

### Analysis

Here we use the example provided in the `doc` directory. First `cd doc` to enter the directory, then call the following command in terminal:

```bash
opu_analysis example.json \
	-b 5.0 -L 400 -H 1800 -N l2 \
	--metric cosine \
	--cutoff-threshold 0.7 \
	--opu-min-size 0.05 \
	--opu-labels example.json.opu_labels.txt \
	--opu-collection-prefix example.json.opu_collection \
	--opu-hca-plot example.json.hca.png \
	--abund-table example.json.opu_abund.tsv \
	--abund-alpha-diversity example.json.opu_alpha_diversity.tsv \
	--abund-stackbar-plot example.json.opu_abund.png \
	--abund-biplot example.json.opu_pca.png \
	--feature-rank-method fisher_score \
	--feature-rank-table example.json.opu_feature_rank.tsv \
	--feature-rank-plot example.json.opu_feature_rank.png
```

A full set of output will be generated in the `doc` folder.


## Convert LabSpec txt Dumps

Data in LabSpec txt dump format needs to be converted into the tabular format. The LabSpec format is 2-column tab-delimited table, similar to followings:

```text
401.23	0.39
402.56	0.01
...
```

The first column is wavenumber and the second column is intensity, and each file encodes only one spectrum. To convert multiple spectra into a single file, first organize them under a same directory (e.g. `inputdir`), and run following:

```bash
opu_dataset_manip from_labspec \
	-x txt -b 5 -L 400 -H 1800 -N l2 \
	-o output.data.tsv \
	inputdir
```

The program will scan the `inputdir` folder and discover all files with an extension of `txt`, then combine them into a single file `output.data.tsv`. Other parameters in the above example instruct the program to bin the wavenumbers using a window size of 5, extract only the 400-1800 cm-1 wavenumber range, and do an l2-normalization per spectrum. These additional data processing parameters are optional, however the binning parameter (-b/--bin-size) is high recommended. This option will force aligning and unify the wavenumbers dicovered in multiple spectrum files. In case the bin size is not given (indicating no binning will be performed) but the wavenumbers in different input spetrum files are different, an error will occur.


# Jupyter Notebook Usage

To use this package in Jupyter notebook or as a library for integrating with other analysis pipelines, simply do:

```python
from opu_analysis_lib import OPUAnalysis
```

The detailed analysis and function calls are stated in `doc/example.ipynb`.
