#!/usr/bin/env python3

import abc

import numpy

# custom lib
from . import registry, util


class CustomRegistry(registry.Registry):
	def list_keys(self):
		return sorted([k for k in self.keys() if k != "*"])

	def get(self, key, *ka, **kw):
		if key == "*":
			raise ValueError("key '*' cannot be used as direct query")
		elif isinstance(key, float):
			ret = super().get("*", *ka, **kw)
		else:
			ret = super().get(key, *ka, **kw)
		return ret

	def argparse_type(self, value):
		if value in self.list_keys():
			ret = value
		else:
			ret = util.NonNegFloat(value)
		return ret


class HCACutoffOptimizer(object):
	@abc.abstractmethod
	def optimize(self, *, model, data, dist, cutoff_list, cutoff_pend, **kw):
		pass

	@property
	@abc.abstractmethod
	def cutoff_final_str(self) -> str:
		pass


_reg = registry.new(registry_name="hca_cutoff_optimizer",
	reg_type=CustomRegistry,
	value_type=HCACutoffOptimizer)


@_reg.register("*")
class FloatPlain(HCACutoffOptimizer):
	def optimize(self, *, cutoff_pend, **kw):
		self.cutoff_final = cutoff_pend
		return

	@property
	def cutoff_final_str(self) -> float:
		return "%.2f" % self.cutoff_final


@_reg.register("aic")
class AIC(HCACutoffOptimizer):
	def optimize(self, *, model, data, dist, cutoff_list, **kw):
		sigma = numpy.median(data.std(axis=0))
		aic_list = [self._calc_aic(model, data, dist, i, sigma)
			for i in cutoff_list]
		# find the cutoff with least aic
		self.cutoff_final = cutoff_list[numpy.argmin(aic_list)]
		return

	def _calc_aic(self, model, data, dist, cutoff, sigma):
		# adjust parameter and fit model
		model.set_params(distance_threshold=cutoff)
		model.fit(dist)
		# calculate aic
		d = data.shape[1]
		uniq_labels = numpy.unique(model.labels_)
		ret = 0
		for l in uniq_labels:
			cluster_points = data[model.labels_ == l]
			cluster_points -= cluster_points.mean(axis=0, keepdims=True)
			ret += ((cluster_points / sigma) ** 2).sum()
		ret += 2 * d * model.n_clusters_
		return ret

	@property
	def cutoff_final_str(self) -> str:
		return "%.2f(AIC)" % self.cutoff_final


@_reg.register("bic")
class BIC(HCACutoffOptimizer):
	def optimize(self, *, model, data, dist, cutoff_list, **kw):
		sigma = numpy.median(data.std(axis=0))
		bic_list = [self._calc_bic(model, data, dist, i, sigma)
			for i in cutoff_list]
		# find the cutoff with least bic
		self.cutoff_final = cutoff_list[numpy.argmin(bic_list)]
		return

	def _calc_bic(self, model, data, dist, cutoff, sigma):
		# adjust parameter and fit model
		model.set_params(distance_threshold=cutoff)
		model.fit(dist)
		# calculate bic
		n, d = data.shape
		uniq_labels = numpy.unique(model.labels_)
		ret = 0
		for l in uniq_labels:
			cluster_points = data[model.labels_ == l]
			cluster_points -= cluster_points.mean(axis=0, keepdims=True)
			ret += ((cluster_points / sigma) ** 2).sum()
		ret += n * model.n_clusters_ * numpy.log(d)
		return ret

	@property
	def cutoff_final_str(self) -> str:
		return "%.2f(BIC)" % self.cutoff_final
