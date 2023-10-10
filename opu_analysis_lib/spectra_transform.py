#!/usr/bin/env python3

import argparse
import os
import sys

from . import util
from .spectra_dataset import SpectraDataset


class SpecFromLabspecTxt(object):
	@classmethod
	def cli_get_args(cls, argv_override=None):
		ap = argparse.ArgumentParser(description="discover LabSpec txt dumps in"
			" <datadir> and combine them into a single tabular format file. "
			"LabSpec txt dump is in a 2-column tab-delimited tabular format. "
			"Its first column is wavenumber and the second is intensity. The "
			"format after transformation is a single-piece tabular format, and "
			"the first row is wavenumber, the rest rows are intensities. NOTE: "
			"LabSpec txt dumps from different runs/settings can have different "
			"wavenumbers, in which case the --bin-size/-b option is required to"
			" force aligning the wavenumbers."
		)
		ap.add_argument("datadir", type=str,
			help="input directory to scan LabSpec txt dumps")
		ap.add_argument("--extension", "-x", type=str, default=".txt",
			metavar="str",
			help="the extension of target files process [.txt]")
		ap.add_argument("--recursive", "-r", action="store_true",
			help="also search subdirectories of <datadir> [no]")
		ap.add_argument("--verbose", "-v", action="store_true",
			help="increase verbosity [off]")
		ap.add_argument("--delimiter", "-d", type=str, default="\t",
			metavar="char",
			help="delimiter in text-based input and output [<tab>]")
		ap.add_argument("--output", "-o", type=str, default="-",
			metavar="tsv",
			help="output dataset file [<stdout>]")

		ag = ap.add_argument_group("binning and normalization")
		ag.add_argument("--bin-size", "-b", type=util.PosFloat, default=None,
			metavar="float",
			help="bin size to reconcile wavenumbers in multiple datasets, if left "
				"default, no binning will be performed [off]")
		ag.add_argument("--wavenum-low", "-L", type=util.PosFloat,
			default=400, metavar="float",
			help="lower boundry of wavenumber of extract for analysis [400]")
		ag.add_argument("--wavenum-high", "-H", type=util.PosFloat,
			default=1800, metavar="float",
			help="higher boundry of wavenumber of extract for analysis [1800]")
		ag.add_argument("--normalize", "-N", type=str,
			default=SpectraDataset.norm_meth.default_key,
			choices=SpectraDataset.norm_meth.list_keys(),
			help="normalize method after loading/binning/filtering dataset [%s]"
				% SpectraDataset.norm_meth.default_key)

		# parse and refine args
		args = ap.parse_args()
		# need to add extension separator (usually .) if not so
		# this is require to make compatibility using os.path.splitext()
		if not args.extension.startswith(os.extsep):
			args.extension = os.extsep + args.extension
		if args.output == "-":
			args.output = sys.stdout
		return args

	@classmethod
	def iter_file_by_ext(cls, path, ext, *, recursive=False) -> iter:
		for i in os.scandir(path):
			if i.is_dir() and recursive:
				yield from cls.iter_file_by_ext(i, ext, recursive=recursive)
			elif i.is_file() and os.path.splitext(i.path)[1] == ext:
				yield i.path
		return

	@classmethod
	def read_and_combine_labspec_txt_dumps(cls, path, ext, *, recursive=False,
			delimiter="\t", bin_size=None, wavenum_low=None, wavenum_high=None,
			normalize=SpectraDataset.norm_meth.default_key,
		) -> SpectraDataset:
		# read files in directory
		spectra = [SpectraDataset.from_labspec_txt_dump(i,
				delimiter=delimiter, spectrum_name=os.path.basename(i),
				bin_size=bin_size, wavenum_low=wavenum_low,
				wavenum_high=wavenum_high,
			) for i in cls.iter_file_by_ext(path, ext, recursive=recursive)]
		# concatenate into a single dataset
		dataset = SpectraDataset.concatenate(*spectra)
		return dataset

	@classmethod
	def cli_main(cls, argv_override=None):
		args = cls.cli_get_args(argv_override=argv_override)
		dataset = cls.read_and_combine_labspec_txt_dumps(
			args.datadir, args.extension,
			recursive=args.recursive, delimiter=args.delimiter,
			bin_size=args.bin_size, wavenum_low=args.wavenum_low,
			wavenum_high=args.wavenum_high, normalize=args.normalize)
		dataset.save_file(args.output, delimiter=args.delimiter,
			with_spectra_names=True)
		return
