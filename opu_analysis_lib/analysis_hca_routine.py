#!/usr/bin/env python3

import sys
import typing

import matplotlib
import matplotlib.cm
import matplotlib.colors
import matplotlib.patches
import matplotlib.pyplot
import numpy
import os
import scipy.cluster

# custom lib
import mpllayout

from . import future  # import sklearn.cluster.AgglomerativeClustering here
from . import registry, util
from .analysis_dataset_routine import AnalysisDatasetRoutine


class AnalysisHCARoutine(AnalysisDatasetRoutine):
	"""
	hierarchical clustering analysis routines, including run the clustering,
	save labels and plot heatmap/dendrogram figure
	"""
	metric_reg = registry.get("cluster_metric")
	cutoff_opt_reg = registry.get("hca_cutoff_optimizer")

	def __init__(self, *ka, opu_colors: typing.Optional[list] = None, **kw):
		super().__init__(*ka, **kw)
		self.opu_colors = opu_colors
		return

	class NoOPUError(RuntimeError):
		pass

	@property
	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def cutoff(self):
		return self.cutoff_opt.cutoff_final

	@property
	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def hca_labels(self) -> int:
		return self.hca.labels_

	@property
	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def n_clusters(self) -> int:
		return self.hca_labels.max() + 1

	@property
	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def hca_label_remap(self) -> dict:
		return self._label_remap

	@property
	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def remapped_hca_label(self) -> list:
		"""
		remapped_hca_label will only report clusters which have spectra
		count more than <opu_min_size> used when calling run_hca() in addition,
		the remapped label is also sorted in descending order by count, meaning
		that the lower the label value, larger the cluster
		"""
		return [self.hca_label_remap.get(i, None) for i in self.hca_labels]

	@property
	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def remapped_hca_label_unique(self) -> list:
		# this sort lambda ensures that None will not raise an error and
		# is always at the end of this array
		# None represents the opu "label" of small clusters
		return sorted(set(self.remapped_hca_label),
			key=lambda x: sys.maxsize if x is None else x)

	def run_hca(self, *, metric=metric_reg.default_key, cutoff=0.7,
			linkage="average", max_n_opus=0,
			opu_min_size: typing.Union[str, int, float, None] = None):
		# create the hca object
		self.metric = self.metric_reg.get(metric)
		self.cutoff_opt = self.cutoff_opt_reg.get(cutoff)
		self.cutoff_pend = cutoff
		self.linkage = linkage
		self.max_n_opus = max_n_opus
		self.__parse_and_store_opu_min_size(opu_min_size)
		self.hca = future.sklearn_cluster_AgglomerativeClustering(
			linkage=self.linkage, metric="precomputed",
			# metric="precomputed" as we manually compute the distance matrix
			# note that old scikit-learn library (pre 23.0.0) uses 'affinity'
			# using 'metric' keyword here will raise an error
			distance_threshold=0, n_clusters=None
			# distance_threshold=0 is a placeholer, it will be replaced by
			# cutoff_opt.cutoff_final when optimization is finished
		)
		# calculate distance matrix
		self.dist_mat = self.metric(self.dataset.intens)
		# find the cutoff
		cutoff_final = self.__optimize_cutoff(n_step=100)
		# calculate clusters, using sklearn's backend
		self.hca.set_params(distance_threshold=cutoff_final)
		self.hca.fit(self.dist_mat)
		# calculate linkage matrix
		self.linkage_matrix = self.__calc_linkage_matrix(self.hca)
		# make dendrogram using scipy's backend
		self.dendrogram = scipy.cluster.hierarchy.dendrogram(
			self.linkage_matrix, orientation="right",
			no_plot=True
		)
		# sort opu labels
		self.__sort_and_filter_cluster_labels(self.hca.labels_)
		return self

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def count_biosample_hca_labels(self) -> dict:
		"""
		count the number of raw hca labels in each biosample, return as a dict
		of counters; the keys are biosample names
		"""
		ret = dict()
		biosample = numpy.asarray(self.biosample, dtype=object)
		for s in self.biosample_unique:
			ret[s] = future.Counter(self.hca_labels[biosample == s])
		return ret

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def save_opu_labels(self, f, *, delimiter="\t"):
		if not f:
			return
		with util.get_fp(f, "w") as fp:
			for i in zip(self.dataset.spectra_names, self.remapped_hca_label):
				name, label = i
				# if a label is None (when cluster size below opu_min_size),
				# write the label as "-" instead
				l = str("-" if label is None else label)
				print((delimiter).join([name, str(l)]), file=fp)
		return

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def save_opu_collections(self, prefix, *, delimiter="\t",
			with_spectra_names=True):
		if not prefix:
			return
		# if prefix is a directory alike, omitting the leading '.'
		if prefix.endswith(os.path.sep):
			fn_pattern = "OPU_%02u.txt"
		else:
			fn_pattern = ".OPU_%02u.txt"
		# create one file for each opu
		for label in self.remapped_hca_label_unique:
			if label is not None:
				mask = numpy.equal(self.remapped_hca_label, label)
				file_name = prefix + (fn_pattern % label)
				self.dataset.get_sub_dataset(mask).save_file(file_name,
					delimiter=delimiter, with_spectra_names=with_spectra_names
				)
		return

	@util.with_check_data_avail(check_data_attr="hca", dep_method="run_hca")
	def plot_opu_hca(self, *, plot_to="show", dpi=300):
		if plot_to is None:
			return
		# create figure layout
		layout = self.__create_layout()
		figure = layout["figure"]
		figure.set_dpi(dpi)

		# plot heatmap
		ax = layout["heatmap"]
		self.__plot_heatmap(ax, layout["colorbar"])

		# plot dendrogram
		ax = layout["dendro"]
		self.__plot_dendrogram(ax, i2d_ratio=layout["dendro_i2d"])
		ax.axvline(self.cutoff, linestyle="-", linewidth=1.0,
			color="#ff0000", zorder=4)

		# plot pbar
		self.__plot_hca_cluster_bar(layout["pbar_l"])
		self.__plot_hca_cluster_bar(layout["pbar_r"])

		# plot group bar
		self.__plot_hca_biosample_bar(layout["biosample_bar"])

		# plot group legend
		# plot_group_legend(layout["dendro"], group_data = group_data)

		# misc
		figure.suptitle("OPU clustering (hierarchical)\n"
			"metric=%s; linkage=%s; cutoff=%s; raw clusters=%u; "
			"OPU min. size=%u"
			% (self.metric.name_str, self.linkage,
				self.cutoff_opt.cutoff_final_str, self.n_clusters,
				self.opu_min_size,
			), fontsize=16
		)

		# save fig and clean up
		if plot_to == "show":
			matplotlib.pyplot.show()
			ret = None
		if plot_to == "jupyter":
			ret = None
		else:
			figure.savefig(plot_to, dpi=dpi)
			matplotlib.pyplot.close()
			ret = None
		return ret

	@property
	def cluster_colors(self) -> util.CyclicIndexedList:
		if self.opu_colors:
			colors = self.opu_colors
		else:
			# get preliminary colors by internal colormaps
			prelim = future.get_mpl_cmap("Set3").colors \
				+ future.get_mpl_cmap("Set2").colors
			# + future.get_mpl_cmap("Accent").colors[:-1]
			# + future.get_mpl_cmap("Set3").colors\
			# + future.get_mpl_cmap("Set2").colors\
			# translate to color hex colors and remove identical colors
			colors = util.drop_replicate(map(matplotlib.colors.to_hex, prelim))
		return util.CyclicIndexedList(colors)

	def __parse_and_store_opu_min_size(self, raw_value=None):
		# convert non-real value into real
		if raw_value is None:
			v = int(0)
		elif isinstance(raw_value, str):
			v = float(raw_value)
		else:
			v = raw_value
		# parse float (fraction) into int
		# this section contains type check as well
		try:
			if int(v) == v:  # int
				ret = util.NonNegInt(v)
			else:  # float with decimal
				v = util.Fraction(v)
				ret = int(numpy.math.ceil(v * self.dataset.n_spectra))
		except ValueError:
			raise ValueError("opu_min_size must be non-negative integer or "
				"float between 0 and 1, got '%s'" % raw_value)
		# record to self object
		self.opu_min_size = ret
		return ret

	@staticmethod
	def __calc_linkage_matrix(hca):
		# this function is adapted from:
		# 'https://scikit-learn.org/stable/auto_examples/cluster/plot_agglomerative_dendrogram.html' as of version 1.1.1
		# create the counts of samples under each node
		counts = numpy.zeros(hca.children_.shape[0])
		n_samples = len(hca.labels_)
		for i, merge in enumerate(hca.children_):
			current_count = 0
			for child_idx in merge:
				if child_idx < n_samples:
					current_count += 1  # leaf node
				else:
					current_count += counts[child_idx - n_samples]
			counts[i] = current_count

		linkage_matrix = numpy.column_stack(
			[hca.children_, hca.distances_, counts]
		).astype(float)
		return linkage_matrix

	def __optimize_cutoff(self, n_step=100) -> float:
		# in usual cases, this should only be called by self.run_hca()
		cutoff_list = numpy.linspace(
			self.dist_mat.min(),
			self.dist_mat.max(),
			n_step
		)
		self.cutoff_opt.optimize(
			model=self.hca,
			data=self.dataset.intens,
			dist=self.dist_mat,
			cutoff_list=cutoff_list,
			cutoff_pend=self.cutoff_pend
		)
		return self.cutoff_opt.cutoff_final

	def __sort_and_filter_cluster_labels(self, hca_labels) -> None:
		# two logics implemented here:
		# (1) sort the opu labels based on their size in descensing order
		# (2) assign new opu labels to the ordered labels, the largest is 0,
		# the second largest is 1, etc., and the new labels are used for output;
		# self._label_remap stores this label translation information, so that
		# the new labels can be found using the internal labels (as originally
		# generated by hca)
		sorted_labels = future.Counter(hca_labels).most_common()
		label_remap = dict()
		for i, (label, count) in enumerate(sorted_labels):
			# check if hit the max_n_opus already, if self.max_n_opus is not 0
			if self.max_n_opus and (i >= self.max_n_opus):
				break
			if count >= self.opu_min_size:
				label_remap[label] = i

		# check if all opu sizes below self.min_opu_size
		if not label_remap:
			raise AnalysisHCARoutine.NoOPUError("no OPU found since all HCA "
				"clusters are below the size threshold set; try reduce the "
				"value of min_opu_size")

		self._label_remap = label_remap

		return

	def __create_layout(self, legend_space=1.0) -> dict:
		lc = mpllayout.LayoutCreator(
			left_margin=0.2,
			right_margin=legend_space + 0.2,
			top_margin=0.7,
			bottom_margin=0.5,
		)

		pbar_width = 0.6
		biosample_bar_width = 0.2
		noise_bar_width = 0.2
		cbar_height = 0.4
		heatmap_size = 8.0
		dendro_width = 2.5
		axes_gap = 0.1

		pbar_l = lc.add_frame("pbar_l")
		pbar_l.set_anchor("bottomleft", offsets=(0, pbar_width + axes_gap))
		pbar_l.set_size(pbar_width, heatmap_size)

		heatmap = lc.add_frame("heatmap")
		heatmap.set_anchor("bottomleft", ref_frame=pbar_l,
			ref_anchor="bottomright", offsets=(axes_gap, 0))
		heatmap.set_size(heatmap_size, heatmap_size)

		colorbar = lc.add_frame("colorbar")
		colorbar.set_anchor("topleft", ref_frame=heatmap,
			ref_anchor="bottomleft", offsets=(0, -axes_gap))
		colorbar.set_size(heatmap_size, cbar_height)

		pbar_r = lc.add_frame("pbar_r")
		pbar_r.set_anchor("bottomleft", ref_frame=heatmap,
			ref_anchor="bottomright", offsets=(axes_gap, 0))
		pbar_r.set_size(pbar_width, heatmap_size)

		biosample_bar = lc.add_frame("biosample_bar")
		biosample_bar.set_anchor("bottomleft", ref_frame=pbar_r,
			ref_anchor="bottomright", offsets=(axes_gap / 2, 0))
		biosample_bar.set_size(biosample_bar_width, heatmap_size)

		dendro = lc.add_frame("dendro")
		dendro.set_anchor("bottomleft",
			ref_frame=biosample_bar,
			ref_anchor="bottomright", offsets=(axes_gap, 0))
		dendro.set_size(dendro_width, heatmap_size)

		# create layout
		layout = lc.create_figure_layout()
		layout["dendro_i2d"] = dendro.get_width() / dendro.get_height()

		# apply axes style
		for n in ["colorbar", "biosample_bar", "dendro"]:
			axes = layout[n]
			for sp in axes.spines.values():
				sp.set_visible(False)
			axes.set_facecolor("#f0f0f8")

		for n in ["pbar_l", "pbar_r"]:
			axes = layout[n]
			for sp in axes.spines.values():
				sp.set_edgecolor("#c0c0c0")
			axes.set_facecolor("#f0f0f8")

		for n in ["pbar_l", "heatmap", "colorbar", "pbar_r", "biosample_bar"]:
			axes = layout[n]
			axes.tick_params(
				left=False, labelleft=False,
				right=False, labelright=False,
				bottom=False, labelbottom=False,
				top=False, labeltop=False
			)
		layout["dendro"].tick_params(
			left=False, labelleft=False,
			right=False, labelright=False,
			bottom=True, labelbottom=True,
			top=False, labeltop=False
		)

		return layout

	def __plot_heatmap(self, heatmap_axes, colorbar_axes) -> dict:
		# heatmap
		ax = heatmap_axes
		heatmap_data = self.metric.to_plot_data(self.dist_mat)
		pcolor = ax.pcolor(heatmap_data[numpy.ix_(self.dendrogram["leaves"],
			self.dendrogram["leaves"])], cmap=self.metric.cmap,
			vmin=self.metric.vmin, vmax=self.metric.vmax)
		#
		ax.set_xlim(0, self.dataset.n_spectra)
		ax.set_ylim(0, self.dataset.n_spectra)

		# colorbar
		ax = colorbar_axes
		cbar = colorbar_axes.figure.colorbar(pcolor, cax=ax,
			ticklocation="bottom", orientation="horizontal")
		# misc
		cbar.outline.set_visible(False)
		cbar.set_label(self.metric.name_str, fontsize=14)

		ret = dict(heatmap=pcolor, colorbar=cbar)
		return ret

	def __dendro_get_adjusted_dmax(self, dmax, i2d_ratio) -> float:
		return dmax / (1 - 1 / (2 * self.dataset.n_spectra * i2d_ratio))

	def __plot_dendrogram(self, ax, *, i2d_ratio: float) -> list:
		lines = list()  # the return list containing all lines drawn
		for xys in zip(self.dendrogram["dcoord"], self.dendrogram["icoord"]):
			line = matplotlib.lines.Line2D(*xys, linestyle="-",
				linewidth=1.0, color="#4040ff", zorder=3)
			ax.add_line(line)
			lines.append(line)
		# misc
		ax.grid(axis="x", linestyle="-", linewidth=1.0, color="#ffffff",
			zorder=2)
		ax.set_xlim(0, self.__dendro_get_adjusted_dmax(
			dmax=numpy.max(self.dendrogram["dcoord"]),
			i2d_ratio=i2d_ratio)
		)
		ax.set_ylim(0, 10 * self.dataset.n_spectra)

		return lines

	def __plot_hca_cluster_bar(self, ax):
		remapped_hca_label = self.remapped_hca_label
		color_list = self.cluster_colors
		for i, leaf in enumerate(self.dendrogram["leaves"]):
			label = remapped_hca_label[leaf]
			facecolor = "#ffffff" if label is None else color_list[label]
			patch = matplotlib.patches.Rectangle((0, i), 1, 1,
				edgecolor="none", facecolor=facecolor
			)
			ax.add_patch(patch)
		# add label
		ax.text(0.5, 0.0, "OPU ", fontsize=12, rotation=90,
			horizontalalignment="center", verticalalignment="top"
		)

		ax.set_xlim(0, 1)
		ax.set_ylim(0, self.dataset.n_spectra)
		return

	def __plot_hca_biosample_bar(self, ax):
		for i, leaf in enumerate(self.dendrogram["leaves"]):
			patch = matplotlib.patches.Rectangle((0, i), 1, 1,
				edgecolor="none", facecolor=self.biosample_color[leaf]
			)
			ax.add_patch(patch)
			# add label
			ax.text(0.5, 0.0, "biosample ", fontsize=12, rotation=90,
				horizontalalignment="center", verticalalignment="top"
			)

		ax.set_xlim(0, 1)
		ax.set_ylim(0, self.dataset.n_spectra)
		return
