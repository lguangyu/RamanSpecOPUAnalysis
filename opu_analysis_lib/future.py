#!/usr/bin/env python3

import collections
import inspect

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

