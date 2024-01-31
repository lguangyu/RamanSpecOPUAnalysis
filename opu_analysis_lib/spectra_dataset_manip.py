#!/usr/bin/env python3

import abc
import argparse
import os
import shutil
import sys

from . import registry
from . import cli_util
from .spectra_dataset import SpectraDataset


class SpecDatasetManip(object):
	class SubCmd(abc.ABC):
		def __init__(self, args: argparse.Namespace, *ka, **kw):
			super().__init__(*ka, **kw)
			self.args = args
			return

		@abc.abstractclassmethod
		def add_subparser_args(cls, sp: cli_util.ArgumentParser):
			pass

		@abc.abstractmethod
		def run(self):
			pass

	# the dict to store subcmd_name: str -> subcmd: SubCmd
	# should be manipulated only by add_subcmd() decorator
	__subcmd = registry.new(registry_name="dataset_manip_subcmd",
		value_type=SubCmd)

	@classmethod
	def add_subcmd(cls, name: str):
		return cls.__subcmd.register(key=name)

	@classmethod
	def cli_get_args(cls, argv_override=None):
		ap = cli_util.ArgumentParser(description="calling sub-command to "
			"manipulate spectra dataset(s)")

		# add sub-command parsers
		sp = ap.add_subparsers(dest="command", help="run sub-command",
			parser_class=cli_util.ArgumentParser)
		for k in cls.__subcmd.list_keys():
			p = sp.add_parser(k)
			subcmd = cls.__subcmd.get(k, instantiate=False)
			subcmd.add_subparser_args(p)

		# parse and refine args
		args = ap.parse_args()
		return args

	@classmethod
	def cli_main(cls, argv_override=None):
		args = cls.cli_get_args(argv_override=argv_override)
		return cls.__subcmd.get(args.command, args=args).run()


@SpecDatasetManip.add_subcmd("convert")
class SpecDatasetManipSubCmdConcate(SpecDatasetManip.SubCmd):
	@classmethod
	def add_subparser_args(cls, sp: cli_util.ArgumentParser):
		# add help
		sp.description = "modify dataset(s) by applying binning, normalization"\
			", and band-based filtering; concatenate multiple datasets into "\
			"one if mutliple input files are provided"

		# add args
		sp.add_argument("input", type=str, nargs="+",
			help="input dataset(s) to manipulate")
		sp.add_argument("--output-mode", "-m", type=str, default="concat",
			choices={"concat", "inplace", "separate"},
			help="output mode when processing multiple input files [concat]; "
				"concat: concatenate outputs into one; the output files must "
				"have compatible wavenumbers; inplace: modify input files "
				"inplace, overwrites the input files with new data; separate: "
				"write output files individually into a directory")
		mg = sp.add_mutually_exclusive_group()
		mg.add_argument("--output", "-o", type=str, default=None,
			metavar="tsv",
			help="output dataset file used with '--output-mode=concat' "
				"[<stdout>]")
		mg.add_argument("--output-dir", "-O", type=str, default=None,
			metavar="dir",
			help="dir for output dataset files, must be set if "
				"'--output-mode=separate'")

		sp.add_argument_delimiter()
		sp.add_argument_with_spectra_names()
		sp.add_argument_verbose()

		sp.add_argument_group_binning_and_normalization()
		return

	def _sanitize_args(self):
		args = self.args

		if args.output_mode == "concat":
			if args.output_dir:
				raise ValueError("'--output-mode=concat' cannot be used with "
					"--output-dir/-O")
			elif not args.output:
				# be mercy when --output is not set
				args.output = sys.stdout
			return

		if args.output_mode == "inplace":
			if args.output or args.output_dir:
				raise ValueError("'--output-mode=inplace' mode does not accept "
					"eithe --output/-o or --output-dir/-O")
			return

		if args.output_mode == "separate":
			if (len(args.input) == 1) and (not args.output_dir):
				args.output = sys.stdout  # be mercy when there is only one input
			elif (len(args.input) > 1) and (not args.output_dir):
				raise ValueError("--output-dir/-O must be set with multiple "
					"input files when '--output-mode=separate'")
			return

		return

	def _save_results_concat(self, datasets):
		# this assumes that self.args is sanitized by the self._sanitize_args()
		# and this function should not be called directly
		args = self.args
		d = SpectraDataset.concatenate(*datasets)
		d.save_file(args.output, delimiter=args.delimiter,
			with_spectra_names=True)
		return

	def _save_results_inplace(self, datasets):
		# this assumes that self.args is sanitized by the self._sanitize_args()
		# and this function should not be called directly
		# TODO: change to tempdir solution
		args = self.args
		for d in datasets:
			tmp = d.file + os.path.extsep + "tmp"
			d.save_file(tmp, delimiter=args.delimiter, with_spectra_names=True)
			shutil.move(tmp, d.file)
		return

	def _save_results_separate(self, datasets):
		# this assumes that self.args is sanitized by the self._sanitize_args()
		# and this function should not be called directly
		args = self.args
		if (len(datasets) == 1) and args.output:
			datasets[0].save_file(args.output, delimiter=args.delimiter,
				with_spectra_names=True)
		elif args.output_dir:
			for d in datasets:
				output = os.path.join(args.output_dir, os.path.basename(d.file))
				if os.path.samefile(output, d.file):
					raise IOError("source and output files cannot be the same "
						"when '--output-mode=separate'; use mode 'inplace' if "
						"you want to modify inputs in-place")
				d.save_file(output, delimiter=args.delimiter,
					with_spectra_names=True)
		return

	def run(self):
		args = self.args
		# check args
		# technically this can be done during saving; however, it's better done
		# here before calculations taking place
		self._sanitize_args()

		# run sub-command
		datasets = [SpectraDataset.from_file(i, delimiter=args.delimiter,
			name=i, with_spectra_names=args.with_spectra_names,
			bin_size=args.bin_size, wavenum_low=args.wavenum_low,
			wavenum_high=args.wavenum_high, normalize=args.normalize)
			for i in args.input]

		# save output
		if args.output_mode == "concat":
			self._save_results_concat(datasets)
		elif args.output_mode == "inplace":
			self._save_results_inplace(datasets)
		elif args.output_mode == "separate":
			self._save_results_separate(datasets)
		else:
			raise ValueError("unaccepted output mode: %s" % args.output_mode)
		return
