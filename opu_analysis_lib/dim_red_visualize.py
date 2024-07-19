#!/usr/bin/env python3

import abc
import functools
import warnings

import numpy
import sklearn.base
import sklearn.decomposition

# custom lib
from . import registry


class DimRedVisualize(sklearn.base.TransformerMixin,
		sklearn.base.BaseEstimator):
	def __call__(self, X, Y=None, **kw) -> numpy.ndarray:
		self.set_params(**kw)
		self.prefit_prepare(X, Y)
		self._trans_X = self.fit_transform(X, Y)
		return

	def prefit_prepare(self, X, Y=None) -> None:
		"""
		fill the logics for automatically prepare essential data and parameters
		before calling fit() or fit_transform() methods; leave this empty if no
		such actions are needed;
		"""
		return

	@property
	@abc.abstractmethod
	def sample_points_for_plot(self) -> numpy.ndarray:
		pass

	@property
	@abc.abstractmethod
	def has_feature_points_for_plot(self) -> bool:
		pass

	@property
	def feature_points_for_plot(self) -> numpy.ndarray:
		pass

	@property
	@abc.abstractmethod
	def name_str(self) -> str:
		pass

	@property
	@abc.abstractmethod
	def xlabel_str(self) -> str:
		pass

	@property
	@abc.abstractmethod
	def ylabel_str(self) -> str:
		pass


_reg = registry.new(registry_name="dim_red_visualize",
	value_type=DimRedVisualize)


@_reg.register("pca")
class PCA(DimRedVisualize, sklearn.decomposition.PCA):
	@functools.wraps(sklearn.decomposition.PCA.__init__)
	def __init__(self, *, n_components=2, **kw):
		super().__init__(n_components=n_components, **kw)
		return

	@property
	def sample_points_for_plot(self):
		return self._trans_X[:, :2].T  # (x, y) for transformed x

	@property
	def has_feature_points_for_plot(self):
		return True

	@property
	def feature_points_for_plot(self):
		x_med_norm = numpy.median(numpy.linalg.norm(self._trans_X, ord=1,
			axis=1))
		f_med_norm = numpy.max(numpy.linalg.norm(self.components_.T, ord=1,
			axis=1))
		# return the feature coords scaled to the same magnitude of samples'
		# this benefits biplot
		return self.components_[:2, :].T * x_med_norm / f_med_norm

	@property
	def name_str(self):
		return "PCA"

	@property
	def xlabel_str(self):
		return "PC1 (%.1f%%)" % (self.explained_variance_ratio_[0] * 100)

	@property
	def ylabel_str(self):
		return "PC2 (%.1f%%)" % (self.explained_variance_ratio_[1] * 100)


@_reg.register("t-sne")
class TSNE(DimRedVisualize, sklearn.manifold.TSNE):
	@functools.wraps(sklearn.manifold.TSNE.__init__)
	def __init__(self, *, n_components=2, **kw):
		super().__init__(n_components=n_components, **kw)
		return

	def prefit_prepare(self, X, Y=None):
		# adjust perplexity if it is too large
		if self.perplexity >= X.shape[0]:
			new_value = X.shape[0] - 1  # at least no error
			warnings.warn("perplexity is bound by number of samples, "
				"reduced from %d to %d" % (self.perplexity, new_value))
			self.perplexity = new_value
		# adjust n_iter if X is too large
		if X.shape[0] > 1000:
			self.n_iter = 1000
		return

	@ property
	def sample_points_for_plot(self):
		return self._trans_X[:, :2].T  # (x, y) for transformed x

	@ property
	def has_feature_points_for_plot(self):
		return False

	@ property
	def name_str(self):
		return "t-SNE"

	@ property
	def xlabel_str(self):
		return "t-SNE 1"

	@ property
	def ylabel_str(self):
		return "t-SNE 2"
