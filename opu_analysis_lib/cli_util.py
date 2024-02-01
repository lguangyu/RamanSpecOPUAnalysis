#!/usr/bin/env python3

import argparse

from . import util
from .spectra_dataset import SpectraDataset


class ArgumentParser(argparse.ArgumentParser):
	def add_argument_verbose(self):
		self.add_argument("--verbose", "-v", action="store_true",
			help="increase verbosity [off]")
		return

	def add_argument_delimiter(self):
		self.add_argument("--delimiter", "-d", type=str, default="\t",
			metavar="char",
			help="delimiter used in text-based input(s) and output(s) [<tab>]")
		return

	def add_argument_with_spectra_names(self):
		self.add_argument("--with-spectra-names", "-w", action="store_true",
			default=None,  # none = autodetect
			help="if set, the 1st column in each input file will be considered "
				"as spectra names no matter its content; if not set (default), "
				"the role of the 1st column will be detected automatically")
		return

	def add_argument_group_binning_and_normalization(self):
		ag = self.add_argument_group("binning and normalization")
		ag.add_argument("--bin-size", "-b", type=util.PosFloat, default=None,
			metavar="float",
			help="bin size to reconcile wavenumbers in multiple datasets, if left "
				"default, no binning will be performed [off]")
		ag.add_argument("--wavenum-low", "-L", type=util.NonNegFloat,
			default=400, metavar="float",
			help="lower boundry of wavenumber of extract for analysis [400]; "
				"set 0 to disable this lower-bound filtering")
		ag.add_argument("--wavenum-high", "-H", type=util.NonNegFloat,
			default=1800, metavar="float",
			help="higher boundry of wavenumber of extract for analysis [1800]; "
				"set inf to disable this higher-bound filtering")
		ag.add_argument("--normalize", "-N", type=str,
			default=SpectraDataset.norm_meth.default_key,
			choices=SpectraDataset.norm_meth.list_keys(),
			help="normalize method after loading/binning/filtering dataset [%s]"
				% SpectraDataset.norm_meth.default_key)
		return
