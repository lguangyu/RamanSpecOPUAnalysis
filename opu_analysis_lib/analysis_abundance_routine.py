#!/usr/bin/env python3

import matplotlib
import matplotlib.pyplot
import numpy

# custom lib
import mpllayout

from . import future
from . import registry
from . import util
from .analysis_hca_routine import AnalysisHCARoutine


class AnalysisAbundanceRoutine(AnalysisHCARoutine):
	"""
	routines to calculate OPU abundances in each biosample; most methods of this
	class should be run after AnalysisHCARoutine.run_hca() has been called, and
	the results become available
	"""
	biplot_meth_reg = registry.get("dim_red_visualize")

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def save_opu_abundance_table(self, f, *, delimiter: str = "\t"):
		if not f:
			return
		# calculating biosample opu stats
		biosample_stats = self.__get_biosample_opu_stats()
		hca_label_unique = [i for i in self.remapped_hca_label if i is not None]

		with util.get_fp(f, "w") as fp:
			# header line
			labels = ["other minor" if l is None else ("OPU_%02d" % l)
				for l in self.remapped_hca_label_unique]
			line = delimiter.join([""] + labels)
			print(line, file=fp)
			# for each sample, write a line
			for s in biosample_stats:
				abunds = [str(s["opu_abunds"].get(l, 0))
					for l in self.remapped_hca_label_unique]
				line = delimiter.join([s["name"]] + abunds)
				print(line, file=fp)
		return

	@staticmethod
	def shannon_index(x: numpy.ndarray):
		x = numpy.asarray(x, dtype=float)
		if x.ndim >= 2:
			raise ValueError("the input can only be 1-dim")
		x = x / x.sum()
		# replace the 0s in x with 1; this will not impact the result since
		# ln(1) = 0; when x = 0, we want x * ln(x) be 0 anyway
		x[x == 0] = 1
		si = abs(-(x * numpy.log(x)).sum())  # abs turns -0.0 to 0.0
		return si

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def save_opu_alpha_diversity(self, f, *, delimiter="\t"):
		if not f:
			return

		# calculate alpha diversity
		si_n_minor = self.__calculate_shannon_index(with_minor=False)
		si_w_minor = self.__calculate_shannon_index(with_minor=True)
		# save file
		with util.get_fp(f, "w") as fp:
			# header line
			print(delimiter.join(["", "shannon (OPUs)", "shannon (with minor)"]
				), file=fp)
			# each line for a biosample
			for s, i, j in zip(self.biosample_unique, si_n_minor, si_w_minor):
				print(delimiter.join([s, str(i), str(j)]), file=fp)
		return

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def plot_opu_abundance_stackbar(self, *, plot_to="show", dpi=300):
		if plot_to is None:
			return
		# calculating biosample opu stats
		biosample_stats = self.__get_biosample_opu_stats()
		n_biosample = len(biosample_stats)

		# create layout
		layout = self.__stackbar_create_layout(n_biosample)
		figure = layout["figure"]
		figure.set_dpi(dpi)

		# plot stackbars
		color_list = self.cluster_colors
		handles = list()
		bottom = numpy.zeros(n_biosample, dtype=float)
		x = numpy.arange(n_biosample) + 0.5  # center of each bar
		# plot major opus
		ax = layout["axes"]
		for l in self.remapped_hca_label_unique:
			h = [i["opu_abunds"].get(l, 0) for i in biosample_stats]
			edgecolor = "#404040" if l is None else "none"
			facecolor = "#ffffff" if l is None else color_list[l]
			label = "other minor" if l is None else "OPU_%02u" % l
			bar = ax.bar(x, h, width=0.8, bottom=bottom, align="center",
				edgecolor=edgecolor, linewidth=0.5, facecolor=facecolor,
				label=label
			)
			bottom += h
			handles.append(bar)

		# legend
		ax.legend(handles=handles, loc=2, bbox_to_anchor=(1.02, 1.02),
			fontsize=10, handlelength=0.8, frameon=False,
		)

		# misc
		ax.set_xlim(0, n_biosample)
		ax.set_ylim(0.0, 1.0)
		ax.set_ylabel("OPU abundance", fontsize=12)
		ax.set_xticks(x)
		ax.set_xticklabels([i["name"] for i in biosample_stats], fontsize=10,
			rotation=90
		)

		# save fig and clean up
		if plot_to == "show":
			matplotlib.pyplot.show()
			ret = None
		elif plot_to == "jupyter":
			ret = figure
		else:
			figure.savefig(plot_to, dpi=dpi)
			matplotlib.pyplot.close()
			ret = None
		return ret

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def plot_opu_abundance_biplot(self, *, method=biplot_meth_reg.default_key,
			plot_to="show", label_fontsize=8, dpi=300):
		if plot_to is None:
			return
		if self.n_biosample == 1:
			util.log("biplot skipped since only one biosamples available")
			return

		# calculating biosample opu stats
		biosample_stats = self.__get_biosample_opu_stats()
		n_biosample = len(biosample_stats)
		hca_labels = [i for i in self.remapped_hca_label_unique
			if i is not None]
		n_label = len(hca_labels)

		# abund_mat, n_biosample * n_label
		abund_mat = numpy.empty((n_biosample, n_label), dtype=float)
		for i in range(n_biosample):
			for j, l in enumerate(hca_labels):
				abund_mat[i, j] = biosample_stats[i]["opu_abunds"].get(l, 0)

		# run dimensionality reduction
		biplot_meth = self.biplot_meth_reg.get(method)
		biplot_meth(abund_mat)

		# create layout
		layout = self.__biplot_create_layout()
		figure = layout["figure"]
		figure.set_dpi(dpi)

		# plot biplot, sample
		ax = layout["axes"]
		sample_xy = biplot_meth.sample_points_for_plot
		ax.scatter(*sample_xy, marker="o", s=40, edgecolor="#4040ff",
			linewidth=1.0, facecolor="#ffffff40", zorder=1)
		for xy, s in zip(sample_xy.T, self.biosample_unique):
			ax.text(*xy, s, fontsize=label_fontsize, zorder=3,
				rotation=self.__perp_text_rotation(*xy), rotation_mode="anchor",
				horizontalalignment="center",
				verticalalignment="bottom" if xy[1] >= 0 else "top")

		# plot biplot, feature
		feature_xy = biplot_meth.feature_points_for_plot
		for xy, l in zip(feature_xy, hca_labels):
			# use annotate() to draw arrows acan
			ax.annotate("", xy, (0, 0),
				arrowprops=dict(
					arrowstyle="-|>",
					linewidth=1.5,
					edgecolor="#ffa040",
					facecolor="#ffa040",
				),
				zorder=2,
			)
			ax.text(*xy, "OPU_%02u" % l, fontsize=label_fontsize,
				color="#ff4040", zorder=3,
				rotation=self.__perp_text_rotation(*xy), rotation_mode="anchor",
				horizontalalignment="center",
				verticalalignment=("bottom" if xy[1] >= 0 else "top"))

		# misc
		ax.axvline(0, linestyle="--", linewidth=1.0,
			color="#808080", zorder=1)
		ax.axhline(0, linestyle="--", linewidth=1.0,
			color="#808080", zorder=1)
		coord_max = biplot_meth.sample_points_for_plot.max() * 1.1
		ax.set_xlim(-coord_max, coord_max)
		ax.set_ylim(-coord_max, coord_max)
		ax.set_xlabel(biplot_meth.xlabel_str, fontsize=14)
		ax.set_ylabel(biplot_meth.ylabel_str, fontsize=14)

		# save fig and clean up
		if plot_to == "show":
			matplotlib.pyplot.show()
			ret = None
		elif plot_to == "jupyter":
			ret = figure
		else:
			figure.savefig(plot_to, dpi=dpi)
			matplotlib.pyplot.close()
			ret = None
		return ret

	def __calculate_shannon_index(self, with_minor: bool):
		count_stats = self.count_biosample_hca_labels()
		ret = list()
		for s in self.biosample_unique:
			if with_minor:
				# if with_minor, use all counts
				counts = list(count_stats[s].values())
			else:
				# if not with_minor, ignore minor cluster counts
				counts = [c for l, c in count_stats[s].items()
					if l in self.hca_label_remap
				]
			ret.append(self.shannon_index(counts))
		return ret

	def __get_biosample_opu_stats(self, minor_policy="grouped") -> list:
		"""
		biosample stats based on self.biosample, self.biosample_color, and
		self.remapped_hca_label;
		returns a list of dict elements each represents stats of a biosample, in
		the same order follows the encounting order in self.biosample

		stats include:
		name: biosample name
		n_spectra: number of spectra in that biosample
		color: color of that biosample
		opu_counts: spectra counts in each opu, as in remapped opu labels

		the argument minor_policy determins how to report minor clusters (those
		below the min_opu_size threshold), accepted values are:
		grouped: grouped into a same label 'None' (default)
		hidden: removed from stats
		"""
		if minor_policy not in {"grouped", "hidden"}:
			raise ValueError("argument minor_policy will only accept value "
				"'grouped' or 'hidden', got '%s'" % minor_policy)

		ret = list()
		count_stats = self.count_biosample_hca_labels()
		for s in self.biosample_unique:
			# remap the labels
			opu_counts = future.Counter()
			for label, count in count_stats[s].items():
				remapped_label = self.hca_label_remap.get(label, None)
				if (remapped_label is not None) or (minor_policy != "hidden"):
					opu_counts[remapped_label] += count
			n_spectra = opu_counts.total()
			opu_abunds = {l: c / n_spectra for l, c in opu_counts.items()}
			#
			st = dict(
				name=s,
				color=self.biosample_color_dict[s],
				n_spectra=n_spectra,
				opu_counts=opu_counts,
				opu_abunds=opu_abunds,
			)
			#
			ret.append(st)
		return ret

	def __stackbar_create_layout(self, n_biosample):
		lc = mpllayout.LayoutCreator(
			left_margin=0.7,
			right_margin=1.5,
			top_margin=0.5,
			bottom_margin=2.0,
		)

		axes = lc.add_frame("axes")
		axes.set_anchor("bottomleft")
		axes.set_size(0.2 * n_biosample, 3.0)

		# create layout
		layout = lc.create_figure_layout()

		# apply axes style
		axes = layout["axes"]
		for sp in axes.spines.values():
			sp.set_visible(False)
		axes.set_facecolor("#f0f0f8")
		axes.tick_params(
			left=True, labelleft=True,
			right=False, labelright=False,
			bottom=True, labelbottom=True,
			top=False, labeltop=False
		)

		return layout

	def __biplot_create_layout(self):
		lc = mpllayout.LayoutCreator(
			left_margin=1.0,
			right_margin=0.2,
			top_margin=0.2,
			bottom_margin=0.7,
		)

		axes = lc.add_frame("axes")
		axes.set_anchor("bottomleft")
		axes.set_size(4.0, 4.0)

		# create layout
		layout = lc.create_figure_layout()

		# apply axes style
		axes = layout["axes"]
		for sp in axes.spines.values():
			sp.set_visible(False)
		axes.set_facecolor("#f0f0f8")
		axes.tick_params(
			left=True, labelleft=True,
			right=False, labelright=False,
			bottom=True, labelbottom=True,
			top=False, labeltop=False
		)

		return layout

	@staticmethod
	def __perp_text_rotation(x, y) -> float:
		t_rot_tan = -x / y
		return numpy.math.degrees(numpy.math.atan(t_rot_tan))
