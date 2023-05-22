#!/usr/bin/env python3

import argparse
import sys
import matplotlib
import matplotlib.pyplot
import mpllayout
import numpy

from . import util
from .spectra_dataset import SpectraDataset


class SpecPreview(SpectraDataset):
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

	def plot_preview_overview(self, png, *, dpi=300) -> None:
		# create figure layout
		layout = self.create_layout()
		figure = layout["figure"]
		figure.set_dpi(dpi)

		# plot each spectra, lumped together
		ax = layout["spec"]
		wavenum = self.wavenum
		alpha = numpy.sqrt(1.0 / self.n_spectra)
		for label, intens in zip(self.spectra_names, self.intens):
			ax.plot(wavenum, intens, linestyle="-", linewidth=0.5,
				color="#4040ff", alpha=alpha, zorder=2)
		# add mean line
		ax.plot(wavenum, self.intens.mean(axis=0), linestyle="-", linewidth=0.5,
			color="#000000", zorder=3, label="mean")
		# add x axis line
		ax.axhline(0, linestyle="-", linewidth=1.0, color="#c0c0c0", zorder=1)

		# misc
		ax.set_xlim(self.wavenum_low, self.wavenum_high)
		ax.set_xlabel("Wavenumber (cm$^{-1}$)")
		ax.set_ylabel("Intensity (AU)")
		ax.set_title(self.name)

		# save fig and clean up
		figure.savefig(png)
		matplotlib.pyplot.close()
		return

	def _plot_spectrum(self, png, index: int, *, title=None, dpi=300) -> None:
		# create figure layout
		layout = self.create_layout()
		figure = layout["figure"]
		figure.set_dpi(dpi)

		# plot each spectra, lumped together
		ax = layout["spec"]
		wavenum = self.wavenum
		intens = self.intens[index]
		ax.plot(self.wavenum, self.intens[index], linestyle="-", linewidth=1.0,
			color="#4040ff", zorder=2)
		# add x axis line
		ax.axhline(0, linestyle="-", linewidth=1.0, color="#c0c0c0", zorder=1)

		# misc
		ax.set_xlim(self.wavenum_low, self.wavenum_high)
		ax.set_xlabel("Wavenumber (cm$^{-1}$)")
		ax.set_ylabel("Intensity (AU)")
		ax.set_title(title)

		# save fig and clean up
		figure.savefig(png)
		matplotlib.pyplot.close()
		return

	def plot_preview_spectra(self, prefix, *, dpi=300) -> None:
		for i, n in enumerate(self.spectra_names):
			png = "%s.%04u.png" % (prefix, i)
			title = "%s/%s" % (self.name, n)
			self._plot_spectrum(png, index=i, title=title, dpi=dpi)
		return

	def plot_preview(self, mode, p, *, dpi=300) -> None:
		if mode == "overview":
			self.plot_preview_overview(p, dpi=dpi)
		elif mode == "spectra":
			self.plot_preview_spectra(p, dpi=dpi)
		else:
			raise ValueError("mode can only be 'overview' or 'spectra', "
				"got '%s'" % mode)
		return

	@classmethod
	def cli_get_args(cls, argv_override=None):
		ap = argparse.ArgumentParser()
		ap.add_argument("input", type=str, nargs="?", default="-",
			help="input spectra dataset table")
		ap.add_argument("--delimiter", "-d", type=str, default="\t",
			metavar="char",
			help="delimiter in input [<tab>]")
		ap.add_argument("--preview-mode", "-m", type=str, default="overview",
			choices=["overview", "spectra"],
			help="plot mode; in overview mode, all spectra will be on the same "
				"figure, while in spectra mode, each spectra will have its own "
				"figure [overview]")
		ap.add_argument("--plot", "-p", type=str, required=True,
			metavar="png",
			help="the output plot image file (in overview mode) or the output "
				"path prefix (in spectra mode) (required)")
		ap.add_argument("--dpi", type=util.PosInt, default=300,
			metavar="int",
			help="dpi in plot outputs [300]")

		ag = ap.add_argument_group("dataset reconcile and normalize")
		ag.add_argument("--dataset-name", "-n", type=str,
			metavar="str",
			help="specify a dataset name to show in figure(s)")
		ag.add_argument("--bin-size", "-b", type=util.PosFloat, default=None,
			metavar="float",
			help="bin size to reconcile wavenumbers in multiple datasets, if "
				"left default, no binning will be performed [off]")
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
		if args.input == "-":
			args.input = sys.stdin
		return args

	@classmethod
	def iter_file_by_ext(cls, path, ext, *, recursive=False) -> iter:
		for i in os.scandir(path):
			if i.is_dir() and recursive:
				yield from iter_file_by_ext(i, ext, recursive=recursive)
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
		pv = cls.from_file(args.input, name=args.dataset_name,
			delimiter=args.delimiter, bin_size=args.bin_size,
			wavenum_low=args.wavenum_low, wavenum_high=args.wavenum_high,
			normalize=args.normalize)
		pv.plot_preview(args.preview_mode, args.plot, dpi=args.dpi)
		return
