#!/usr/bin/env python3
# this module includes all compatibility wrappers

import collections
import inspect

import matplotlib.cm
import matplotlib.colors
import sklearn.cluster


def sklearn_cluster_AgglomerativeClustering(*ka, metric=None, **kw):
	cls = sklearn.cluster.AgglomerativeClustering
	if "metric" in inspect.signature(cls.__init__).parameters:
		new = cls(*ka, metric=metric, **kw)
	else:
		new = cls(*ka, affinity=metric, **kw)
	return new


# Counter.total() is available >= 3.10
# need to implement one in case
if hasattr(collections.Counter, "total"):
	Counter = collections.Counter
else:
	class Counter(collections.Counter):
		def total(self):
			return sum(self.values())


def get_mpl_cmap(name: str) -> matplotlib.colors.Colormap:
	# wrapped matplotlib colormap query
	if hasattr(matplotlib, "colormaps"):
		# this seems to be available with matplotlib>=3.5
		# got deprecation warning with version 3.8
		ret = matplotlib.colormaps[name]
	else:
		ret = matplotlib.cm.get_cmap(name)
	return ret
