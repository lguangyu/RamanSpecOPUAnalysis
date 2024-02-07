#!/usr/bin/env python3

import abc
import argparse
import os
import shutil
import sys
import tempfile

import numpy
import matplotlib
import mpllayout

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
		sp = ap.add_subparsers(dest="command", help="run 'command --help' for "
			"details",
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
class SpecDatasetManipSubCmdConvert(SpecDatasetManip.SubCmd):
	@classmethod
	def add_subparser_args(cls, sp: cli_util.ArgumentParser):
		# add help
		sp.description = "modify dataset(s) by applying binning, normalization"\
			", and band-based filtering; can also be used to combine multiple "\
			"datasets into one."

		# add args
		sp.add_argument("input", type=str, nargs="+",
			help="input dataset(s) to manipulate")
		sp.add_argument("--output-mode", "-m", type=str, default="concat",
			choices={"concat", "inplace", "separate"},
			help="output mode to use when processing multiple input files "
				"[concat]; "
				# concat
				"concat (expect to be accompanied with --output/-o): "
				"concatenate all outputs into one, and all output files must "
				"have compatible wavenumbers natively or be forcefully aligned "
				"with a valid --bin-size/-b parameter; "
				# inplace
				"inplace (expect neither --output/-o or --output-dir/-O): "
				"modify input files in-place, overwritting with new data; "
				# separate
				"separate: (expect to be accompanied with --output-dir/-O): "
				"write output files individually into the target directory, "
				"output files will try to replicate the file names of input")
		mg = sp.add_mutually_exclusive_group()
		mg.add_argument("--output", "-o", type=str, default=None,
			metavar="tsv",
			help="a single output dataset file, expected when --output-mode/-m "
				"is 'concat' [<stdout>]; this option cannot be used together "
				"with --output-dir/-O")
		mg.add_argument("--output-dir", "-O", type=str, default=None,
			metavar="dir",
			help="dir to save output dataset files, expected when "
				"--output-mode/-m is 'separate'; this option cannot be used "
				"together with --output/-o")

		sp.add_argument_delimiter()
		sp.add_argument_with_spectra_names()
		sp.add_argument_verbose()

		sp.add_argument_group_binning_and_normalization()
		return

	def _sanitize_args(self):
		args = self.args

		if args.output_mode == "concat":
			if args.output_dir:
				raise ValueError("--output-dir/-O cannot be set when "
					"--output-mode/-m is 'concat'")
			elif not args.output:
				# be mercy when --output is not set
				args.output = sys.stdout
			return

		if args.output_mode == "inplace":
			if args.output or args.output_dir:
				raise ValueError("neither --output/-o or --output-dir/-O can "
					"be set when --output-mode/-m is 'inplace'")
			return

		if args.output_mode == "separate":
			if (len(args.input) == 1) and (not args.output_dir):
				args.output = sys.stdout  # be mercy when there is only one input
			elif (len(args.input) > 1) and (not args.output_dir):
				raise ValueError("--output-dir/-O must be set with multiple "
					"input files when --output-mode/-m is 'separate'")
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
		args = self.args
		with tempfile.TemporaryDirectory() as td:
			for d in datasets:
				tmp = os.path.join(td, os.path.basename(d.file))
				d.save_file(tmp, delimiter=args.delimiter,
					with_spectra_names=True)
				shutil.copy(tmp, d.file)
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
						"when --output-mode/-m is 'separate'; use 'inplace' if "
						"in-place changes are meant")
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


@SpecDatasetManip.add_subcmd("head")
class SpecDatasetManipSubCmdHead(SpecDatasetManip.SubCmd):
	@classmethod
	def add_subparser_args(cls, sp: cli_util.ArgumentParser):
		# add help
		sp.description = "extract the first <n> spectra in a dataset"

		sp.add_argument("input", type=str, nargs="?", default="-",
			help="input dataset extract [stdin]")
		sp.add_argument("--output", "-o", type=str, default="-",
			metavar="tsv",
			help="output dataset [stdout]")
		sp.add_argument("--n-spectra", "-n", type=str, default="10",
			metavar="[-]int",
			help="extract the first <int> spectra from the dataset; with the "
				"leading '-', extract all but the last <int> ones [10]")
		sp.add_argument_delimiter()
		sp.add_argument_with_spectra_names()
		sp.add_argument_verbose()
		return

	def run(self):
		args = self.args
		# refine args
		if args.input == "-":
			args.input = sys.stdin
		if args.output == "-":
			args.output = sys.stdout
		# parse n_spectra
		if args.n_spectra.isdigit():
			rev = False
			n_spectra = int(args.n_spectra)
		elif args.n_spectra.startswith("-") and args.n_spectra[1:].isdigit():
			rev = True
			n_spectra = int(args.n_spectra[1:])
		else:
			raise TypeError("bad --n-spectra/-n format: %s" % args.n_spectra)
		assert n_spectra >= 0

		# extract
		dataset = SpectraDataset.from_file(args.input, delimiter=args.delimiter,
			with_spectra_names=args.with_spectra_names, wavenum_low=0,
			wavenum_high=numpy.inf, normalize="none")
		if not rev:
			# 0 => [:0] => extract nothing
			# 1 => [:1] => extract first one
			# n => [:n] => extract all (first n) spectra
			# bignum => [:bignum] => extract everything
			query = slice(None, n_spectra)
		elif n_spectra == 0:
			# 0 => [:-0] (revise to => [:]/don't touch) => extract everything
			query = slice(None)
		else:
			# 1 => [:-1] => extract all but last 1
			# n => [:-n] => extract nothing
			# bignum => [:-bignum] => extract nothing
			query = slice(None, -n_spectra)
		extract = dataset.get_sub_dataset(query)
		extract.save_file(args.output, delimiter=args.delimiter,
			with_spectra_names=True)
		return


@SpecDatasetManip.add_subcmd("tail")
class SpecDatasetManipSubCmdTail(SpecDatasetManip.SubCmd):
	@classmethod
	def add_subparser_args(cls, sp: cli_util.ArgumentParser):
		# add help
		sp.description = "extract the last <n> spectra in a dataset"

		sp.add_argument("input", type=str, nargs="?", default="-",
			help="input dataset extract [stdin]")
		sp.add_argument("--output", "-o", type=str, default="-",
			metavar="tsv",
			help="output dataset [stdout]")
		sp.add_argument("--n-spectra", "-n", type=str, default="10",
			metavar="[+]int",
			help="extract the last <int> spectra from the dataset; with the "
				"leading '+', extract from line number <int> [10]")
		sp.add_argument_delimiter()
		sp.add_argument_with_spectra_names()
		sp.add_argument_verbose()
		return

	def run(self):
		args = self.args
		# refine args
		if args.input == "-":
			args.input = sys.stdin
		if args.output == "-":
			args.output = sys.stdout
		# parse n_spectra
		if args.n_spectra.isdigit():
			rev = False
			n_spectra = int(args.n_spectra)
		elif args.n_spectra.startswith("+") and args.n_spectra[1:].isdigit():
			rev = True
			n_spectra = int(args.n_spectra[1:])
		else:
			raise TypeError("bad --n-spectra/-n format: %s" % args.n_spectra)
		assert n_spectra >= 0

		# extract
		dataset = SpectraDataset.from_file(args.input, delimiter=args.delimiter,
			with_spectra_names=args.with_spectra_names, wavenum_low=0,
			wavenum_high=numpy.inf, normalize="none")
		if rev:
			# 0 => [0:] => extract everything
			# 1 => [0:] => extract everything
			# n => [n-1:] => extract all but first n-1
			# bignum => [bignum-1:] => extract nothing
			query = slice(max(n_spectra - 1, 0), None)
		elif n_spectra == 0:
			# 0 => [n:] => extract nothing
			query = slice(dataset.n_spectra, None)
		else:
			# 1 => [-1:] => extract last one
			# n => [-n:] => extract all (last n) spectra
			# bignum => [-bignum:] => extract everything
			query = slice(-n_spectra, None)
		extract = dataset.get_sub_dataset(query)
		extract.save_file(args.output, delimiter=args.delimiter,
			with_spectra_names=True)
		return


@SpecDatasetManip.add_subcmd("from_labspec")
class SpecDatasetManipSubCmdFromLabspec(SpecDatasetManip.SubCmd):
	@classmethod
	def add_subparser_args(cls, sp: cli_util.ArgumentParser):
		# add help
		sp.description = "discover LabSpec txt dumps in <datadir> and combine "\
			"them into a single tabular format file. Format of the LabSpec txt"\
			" dump is 2-column tab-delimited table: 1st column is wavenumber "\
			"and 2nd column is intensity. The format after transformation is a"\
			" single-piece tabular format: 1st row is wavenumber, and the rest"\
			" are intensities. NOTE: LabSpec txt dumps from different "\
			"runs/settings can have different wavenumbers, in which case the "\
			"--bin-size/-b option is required to align the wavenumbers."
		sp.add_argument("datadir", type=str,
			help="input directory to scan for LabSpec txt dumps")
		sp.add_argument("--extension", "-x", type=str, default=".txt",
			metavar="str",
			help="the extension of target files process [.txt]")
		sp.add_argument("--recursive", "-r", action="store_true",
			help="also search subdirectories of <datadir> [no]")
		sp.add_argument("--output", "-o", type=str, default="-",
			metavar="tsv",
			help="output dataset file [<stdout>]")
		sp.add_argument_delimiter()
		sp.add_argument_verbose()

		sp.add_argument_group_binning_and_normalization()
		return

	@classmethod
	def _iter_file_by_ext(cls, path, ext, *, recursive=False) -> iter:
		for i in os.scandir(path):
			if i.is_dir() and recursive:
				yield from cls._iter_file_by_ext(i, ext, recursive=recursive)
			elif i.is_file() and os.path.splitext(i.path)[1] == ext:
				yield i.path
		return

	def run(self):
		args = self.args
		# refine args
		if args.output == "-":
			args.output = sys.stdout

		# run sub-command
		# read files in directory
		file_iter = self._iter_file_by_ext(args.datadir, args.extension,
			recursive=args.recursive)
		spectra = [SpectraDataset.from_labspec_txt_dump(i,
			delimiter=args.delimiter, spectrum_name=os.path.basename(i),
			bin_size=args.bin_size, wavenum_low=args.wavenum_low,
			wavenum_high=args.wavenum_high)
			for i in file_iter]
		# concatenate into a single dataset
		dataset = SpectraDataset.concatenate(*spectra)
		dataset.save_file(args.output, delimiter=args.delimiter,
			with_spectra_names=True)
		return


@SpecDatasetManip.add_subcmd("preview")
class SpecDatasetManipSubCmdPreview(SpecDatasetManip.SubCmd):
	@classmethod
	def add_subparser_args(cls, sp: cli_util.ArgumentParser):
		# add help
		sp.description = "preview the dataset for visual inspection"

		sp.add_argument("input", type=str, nargs="?", default="-",
			help="input dataset to visualize")
		sp.add_argument("--preview-mode", "-m", type=str, default="overview",
			choices=["overview", "spectra"],
			help="plot mode; in overview mode, all spectra will be on the same "
				"figure, while in spectra mode, each spectra will have its own "
				"figure [overview]")
		sp.add_argument("--dataset-name", "-n", type=str,
			metavar="str",
			help="specify a dataset name to show in figure(s)")
		sp.add_argument("--plot", "--prefix", "-p", type=str,
			metavar="file/prefix",
			help="in spectra mode: the output image file, can be omitted to "
				"open matploblib's interactive window instead; "
				"spectra mode: required, and will be used as the prefix for "
				"generated files")
		sp.add_argument("--dpi", type=cli_util.util.PosInt, default=300,
			metavar="int",
			help="dpi in plot outputs [300]")
		sp.add_argument_delimiter()
		sp.add_argument_with_spectra_names()
		sp.add_argument_verbose()

		sp.add_argument_group_binning_and_normalization()
		return

	def create_layout(self) -> dict:
		lc = mpllayout.LayoutCreator(
			left_margin=0.7,
			right_margin=0.2,
			top_margin=0.5,
			bottom_margin=0.7,
		)

		ax = lc.add_frame("spec")
		ax.set_anchor("bottomleft")
		ax.set_size(5.0, 1.0)

		# create layout
		layout = lc.create_figure_layout()

		# apply axes style
		ax = layout["spec"]
		for sp in ax.spines.values():
			sp.set_visible(False)
		ax.set_facecolor("#f0f0f8")

		return layout

	def _plot_preview_overview(self, d: SpectraDataset) -> None:
		# create figure layout
		layout = self.create_layout()
		figure = layout["figure"]
		figure.set_dpi(self.args.dpi)

		# plot each spectra, lumped together
		ax = layout["spec"]
		wavenum = d.wavenum
		alpha = numpy.sqrt(1.0 / d.n_spectra)
		for label, intens in zip(d.spectra_names, d.intens):
			ax.plot(wavenum, intens, linestyle="-", linewidth=0.5,
				color="#4040ff", alpha=alpha, zorder=2)
		# add mean line
		ax.plot(wavenum, d.intens.mean(axis=0), linestyle="-", linewidth=0.5,
			color="#000000", zorder=3, label="mean")
		# add x axis line
		ax.axhline(0, linestyle="-", linewidth=1.0, color="#c0c0c0", zorder=1)

		# misc
		ax.set_xlim(d.wavenum_low, d.wavenum_high)
		ax.set_xlabel("Wavenumber (cm$^{-1}$)")
		ax.set_ylabel("Intensity (AU)")
		ax.set_title(d.name)

		# save fig and clean up
		if self.args.plot:
			figure.savefig(self.args.plot, dpi=self.args.dpi)
		else:
			matplotlib.pyplot.show()
		matplotlib.pyplot.close()
		return

	def _plot_spectrum(self, png: str, d: SpectraDataset, index: int, *,
			title=None) -> None:
		# create figure layout
		layout = self.create_layout()
		figure = layout["figure"]
		figure.set_dpi(self.args.dpi)

		# plot each spectra, lumped together
		ax = layout["spec"]
		wavenum = d.wavenum
		intens = d.intens[index]
		ax.plot(d.wavenum, d.intens[index], linestyle="-", linewidth=1.0,
			color="#4040ff", zorder=2)
		# add x axis line
		ax.axhline(0, linestyle="-", linewidth=1.0, color="#c0c0c0", zorder=1)

		# misc
		ax.set_xlim(d.wavenum_low, d.wavenum_high)
		ax.set_xlabel("Wavenumber (cm$^{-1}$)")
		ax.set_ylabel("Intensity (AU)")
		ax.set_title(title)

		# save fig and clean up
		figure.savefig(png, dpi=self.args.dpi)
		matplotlib.pyplot.close()
		return

	def _plot_preview_spectra(self, d: SpectraDataset) -> None:
		prefix = self.args.plot
		for i, n in enumerate(d.spectra_names_with_prefix):
			self._plot_spectrum("%s%04u.png" % (prefix, i), d, i, title=n)
		return

	def plot_preview(self, d: SpectraDataset) -> None:
		args = self.args
		if args.preview_mode == "overview":
			self._plot_preview_overview(d)
		elif args.preview_mode == "spectra":
			self._plot_preview_spectra(d)
		else:
			raise ValueError("mode can only be 'overview' or 'spectra', "
				"not '%s'" % mode)
		return

	def run(self):
		args = self.args
		# refine args
		if args.input == "-":
			args.input = sys.stdin
		if (args.preview_mode == "spectra") and (not args.plot):
			raise ValueError("--prefix/-p is requried in spectra mode")

		dataset = SpectraDataset.from_file(args.input, name=args.dataset_name,
			with_spectra_names=args.with_spectra_names,
			delimiter=args.delimiter, bin_size=args.bin_size,
			wavenum_low=args.wavenum_low, wavenum_high=args.wavenum_high,
			normalize=args.normalize)
		self.plot_preview(dataset)
		return
