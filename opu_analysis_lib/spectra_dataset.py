#!/usr/bin/env python3

import collections
import numbers
import os
import warnings

import numpy

# custom lib
from . import registry, util


class SpectraDataset(object):
	"""
	I/O class for spectra dataset, with additional preprocessing features like
	binning, wavenumber range filtering and normalization

	ARGUMENTS
	=========
	wavenum: 1-d vector of float, the wavenumbers of the spectra; parsed as the
		header line when using SpectraDataset.from_file()
	intens: 2-d vector of float, the intensity matrix of the spectra
	spectra_names: None, str, or list[str];
		None: using numerical ids
		str: using numerical ids with <str> as prefix
		list[str]: using these as spectra ids
	NOTE: shape of intens must be len(spectra_name) * len(wavenum) if
		spectra_names is list[str]

	name: str, dataset name or "unknown_dataset" by default
	wavenum_low: float; deduced from wavenum by default (None)
	wavenum_high: float; deduced from wavenum by default (None)
	"""
	norm_meth = registry.get("normalize")

	def __init__(self, wavenum, intens, *ka, file=None, spectra_names=None,
			name=None, wavenum_low=None, wavenum_high=None, **kw):
		super().__init__(*ka, **kw)
		self.file = file
		self.name = name
		self.set_data(wavenum, intens, spectra_names=spectra_names,
			wavenum_low=wavenum_low, wavenum_high=wavenum_high)
		return

	@property
	def is_empty(self) -> bool:
		return bool(self.n_spectra)

	def set_data(self, wavenum, intens, spectra_names=None, *,
			wavenum_low=None, wavenum_high=None):
		wavenum = numpy.asarray(wavenum, dtype=float)
		intens = numpy.asarray(intens, dtype=float)
		# deduce spectra_names if scalar values are used
		if spectra_names is None:
			# if spectra names are not specified, use simple numberical label
			# prefix = self.name or "unnamed_dataset"
			spectra_names = ["%08u" % (i + 1) for i in range(len(intens))]
			# spectra_names = [(prefix + "_%08u") % (i + 1)
			# for i in range(len(intens))]
		elif isinstance(spectra_names, str):
			# use the spectra_names as prefix if it's str
			prefix = spectra_names
			spectra_names = [(prefix + "_%08u") % (i + 1)
				for i in range(len(intens))]
		elif not isinstance(spectra_names, collections.abc.Iterable):
			raise TypeError("spectra_names must be None, str, or an iterable "
				"object, not %s" % type(spectra_names).__name__)
		# else, keep the same, assuming spectra names
		# spectra_names = spectra_names
		spectra_names = numpy.asarray(spectra_names, dtype=object)
		# check shapes are correct and compatible
		if spectra_names.ndim != 1:
			raise ValueError("spectra_names must be 1-d array")
		if wavenum.ndim != 1:
			raise ValueError("wavenum must be 1-d array")
		if intens.ndim != 2:
			raise ValueError("intens must be 2-d array")
		if spectra_names.shape[0] != intens.shape[0]:
			raise ValueError("spectra_name and intens have unmatched size")
		if wavenum.shape[0] != intens.shape[1]:
			raise ValueError("wavenum and intens have unmatched size")
		# check for spectra name collision
		if (len(spectra_names) != len(set(spectra_names))):
			raise ValueError("looks like there are spectra name collisions "
				"which is probably provided as a list/iterator as the value of "
				"with_spectra_names argument; name collisions must be resolved "
				"to proceed")
		# issue warning if dataset is empty
		if not len(intens):
			warnings.warn("empty dataset (has zero spectrum)")
		# if all ok set object attributes
		self.spectra_names = spectra_names
		self.wavenum = wavenum
		self.intens = intens
		# check wavenumber low and high
		self.wavenum_low = wavenum_low or self.wavenum.min()
		self.wavenum_high = wavenum_high or self.wavenum.max()
		return

	@property
	def spectra_names_with_prefix(self) -> numpy.ndarray:
		"""
		return a list of spectra names prefixed by dataset name if available;
		this can be used to resolve spectra name collision between different
		dataset files; the identical list to self.spectra_names will be returned
		 if dataset name is not available.
		"""
		ret = self.spectra_names
		if self.name:
			ret = numpy.asarray([self.name + "-" + i for i in ret],
				dtype=object)
		return ret

	@classmethod
	def from_file(cls, f: str, *, delimiter="\t", name=None,
			with_spectra_names=None, bin_size=None, wavenum_low=400.0,
			wavenum_high=1800.0, normalize=norm_meth.default_key):
		"""
		read spectra dataset form text file in tabular format
		the read table must have the first line as the wave number (wavnum)
		information; the spectra names are optionl, but they must be available
		in the first column if used

		with_spectra_names: can be None, False, True, or a list of str, behaviour
			depends:
			False: force not parsing the first column as spectra names, and will
				fill out spectra_names attribute by deducing from dataset name
			True: force parsing the first column as spectra names
			None: auto-detect if first column looks like spectra names
			list[str]: if provided, this will override the spectra names despite
				if the spectra names presents in the file; length of the list
				must be the same as number of samples;
		"""
		raw = numpy.loadtxt(f, delimiter=delimiter, dtype=object)
		if ((with_spectra_names is None) and cls._1st_col_looks_names(raw) or
			(with_spectra_names is True)):
			# we only need to parse names from file under these two conditions
			# parse the table except 1st column as data
			wavenum = raw[0, 1:].astype(float)
			intens = raw[1:, 1:].astype(float)
			spectra_names = raw[1:, 0]
		else:
			# use value of with_spectra_names as hit to spectra_names
			# and parse the whole table as data
			wavenum = raw[0, 0:].astype(float)
			intens = raw[1:, 0:].astype(float)
			spectra_names = with_spectra_names  # None, str, list are all safe
		# create return dataset object
		new = cls(wavenum=wavenum, intens=intens, file=f, name=name or f,
			spectra_names=spectra_names)
		new.bin_and_filter_wavenum(bin_size=bin_size, wavenum_low=wavenum_low,
			wavenum_high=wavenum_high, inplace=True)
		new.normalize(normalize, inplace=True)
		return new

	@staticmethod
	def _1st_col_looks_names(raw: numpy.ndarray) -> bool:
		# True if the topleft cell cannot be interpreted as number
		# otherwise, need to do more test
		if not util.str_is_real(raw[0, 0]):
			return True
		# True if the first column cannot be interpreted all as numebrs
		if not all([util.str_is_real(i) for i in raw[1:, 0]]):
			return True
		return False

	def save_file(self, f, *, delimiter="\t", with_spectra_names=False):
		with util.get_fp(f, "w") as fp:
			# header line
			print(delimiter.join(
				([""] if with_spectra_names else [])
				+ [str(i) for i in self.wavenum]
			), file=fp)
			# data section
			for name, data in zip(self.spectra_names, self.intens):
				print(delimiter.join(
					([name] if with_spectra_names else [])
					+ [str(i) for i in data]
				), file=fp)
		return

	def bin_and_filter_wavenum(self, *, bin_size=None, wavenum_low=400.0,
			wavenum_high=1800.0, inplace=False):
		if bin_size is None:
			# if no need to bin, just filter by range
			mask = numpy.logical_and(self.wavenum >= wavenum_low,
				self.wavenum <= wavenum_high)
			wavenum = self.wavenum[mask]
			intens = self.intens[:, mask]
		else:
			# need to bin, find the end points of each bin
			wavenum_bin = numpy.arange(wavenum_low, wavenum_high, bin_size)
			# offset by half bin size to make the final wavenum is the centroid
			# of each bin window
			wavenum = wavenum_bin[:-1] + bin_size / 2
			# calculate the average for each bin window
			bin_label = numpy.digitize(self.wavenum, wavenum_bin)
			intens = [self._safe_ax1_mean(self.intens[:, bin_label == i])
				for i in range(1, len(wavenum_bin))]
			intens = numpy.hstack(intens)
		# make output
		if inplace:
			self.set_data(wavenum, intens, spectra_names=self.spectra_names,
				wavenum_low=wavenum_low, wavenum_high=wavenum_high)
			ret = self
		else:
			ret = type(self)(wavenum, intens, name=self.name,
				spectra_names=self.spectra_names.copy(),
				wavenum_low=wavenum_low, wavenum_high=wavenum_high)
		return ret

	@staticmethod
	def _safe_ax1_mean(arr):
		# this function to suppress numpy warning "mean over empty slice"
		# if ax1 has 0-length, return 0
		if arr.shape[1]:
			ret = arr.mean(axis=1, keepdims=True)
		else:
			ret = numpy.zeros((len(arr), 1), dtype=float)
		return ret

	def normalize(self, method=norm_meth.default_key, *, inplace=False):
		meth = self.norm_meth.get(method)
		intens = meth(self.intens)
		if inplace:
			self.intens = intens
			self.set_data(self.wavenum, intens, self.spectra_names,
				wavenum_low=self.wavenum_low, wavenum_high=self.wavenum_high)
			ret = self
		else:
			ret = type(self)(self.wavenum.copy(), intens, name=self.name,
				spectra_names=self.spectra_names.copy(),
				wavenum_low=wavenum_low, wavenum_high=wavenum_high)
		return ret

	def is_compatible_wavenum(self, other):
		"""
		return true if two SpectraDataset's have compatible wavenumber ranges
		"""
		return (len(self.wavenum) == len(other.wavenum)) and\
			numpy.allclose(self.wavenum, other.wavenum)

	@staticmethod
	def _concatenate_spectra_names(*ka) -> numpy.ndarray:
		# concatenate spectra_names from dataset in ka, try to avoid name
		# collision if possible
		ret = numpy.concatenate([i.spectra_names for i in ka])
		if len(ret) == len(set(ret)):
			return ret
		# otherwise try resolving name collision by adding prefix
		ret = numpy.concatenate([i.spectra_names_with_prefix for i in ka])
		if len(ret) == len(set(ret)):
			return ret
		# raise an error here
		raise ValueError("looks like there are name collisions after "
			"concatenation, and this collision cannot be resolved by adding "
			"the dataset name as a prefix; try setting unique 'name' field "
			"for each concatenated dataset, or manually resolve the name "
			"collision in each dataset")
		return

	@classmethod
	def concatenate(cls, *ka, name=None):
		"""
		concatenate multiple SpectraDataset objects as one
		if any two datasets have incompatible wavenum, ValueError will be raised

		will always return a new instance of SpectraDataset even if only one
		dataset presents in the input
		"""
		if not ka:
			raise ValueError("at least one dataset is requried")
		ref = ka[0]
		for i in ka:
			if not ref.is_compatible_wavenum(i):
				raise ValueError("incompatible wavenum found betweet dataset "
					"'%s' and '%s', run bin_and_filter_wavenum() with bin_size "
					"defined before concatenate can usually avoid this error"
					% (ref.name, i.name))
		concat_intens = numpy.vstack([i.intens for i in ka])
		new = cls(ref.wavenum.copy(), concat_intens,
			spectra_names=cls._concatenate_spectra_names(*ka),
			name=name or "concatenated spctra dataset",
			wavenum_low=min([i.wavenum_low for i in ka]),
			wavenum_high=max([i.wavenum_high for i in ka]),
		)
		return new

	@property
	def n_spectra(self):
		return len(self.intens)

	@property
	def n_wavenum(self):
		return len(self.wavenum)

	def get_sub_dataset(self, query):
		# query: anything that is compatible with numpy.ndarray.__getitem__
		# e.g. a bool sequence, an int sequence, a slice, or an integer.
		if isinstance(query, numbers.Integral):
			# if it's integer, turn it into to be sequence-like
			# i.e. indices = 1 => indicies = [1]
			query = [query]
		intens = self.intens[query, :]
		spectra_names = self.spectra_names[query]
		# the ret spectra dataset with subset data
		ret = type(self)(self.wavenum.copy(), intens,
			spectra_names=spectra_names, name=self.name)
		return ret

	@classmethod
	def from_labspec_txt_dump(cls, f, *, delimiter="\t", spectrum_name=None,
			bin_size=None, wavenum_low=400.0, wavenum_high=1800.0,
			normalize=norm_meth.default_key):
		"""
		read from the .txt dump format from LabSpec; the format should contain
		only one spectrum per file, in a 2-column tab-delimited format, with
		wavenumbers in the first column and intensities in the second column;

		calling this method will read a LabSpec txt dump file and return a
		single-spectrum dataset;

		ARGUMENTS
		---------
		f: file to read, can be already opened file handle or str as file name
		delimiter: delimiter character in the input file, default is <tab>;
			usually this is not the subject to change
		spectrum_name: the name of the spectrum, if not provided, the file path
			(including directory) will be used
		bin_size: window size used in binning, default is not perform binning;
			however, binning may be required to reconcile when join multiple
			spectra unless they have exactly the same wavenumbers
		wavenum_low: the lower wavenumber boundary to extract data
		wavenum_high: the upper wavenumber boundary to extract data
		normalize: if and what normalization should be performed
		"""
		# read data from the text dump
		# use get_fp here is to ensure we can get the file name within the next
		# few lines without another if statement
		with util.get_fp(f, "r") as fp:
			# labspec txt dump contains only 1 spec per file
			if spectrum_name is None:
				spectrum_name = fp.name
			wavenum, intens = numpy.loadtxt(fp, dtype=float,
				delimiter=delimiter, unpack=True)
		new = cls(wavenum, intens.reshape(1, -1), spectra_names=[spectrum_name],
			name=spectrum_name)
		new.bin_and_filter_wavenum(bin_size=bin_size, wavenum_low=wavenum_low,
			wavenum_high=wavenum_high, inplace=True)
		new.normalize(normalize, inplace=True)
		return new
