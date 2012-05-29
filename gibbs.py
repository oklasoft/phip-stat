#! /usr/bin/env python

import os
import sys
import random

import matplotlib as mpl
if __name__ == '__main__':  # if running as script, disable any windowing
    mpl.use('agg')
import matplotlib.pyplot as plt
import matplotlib.colors
import matplotlib.cm

import numpy as np
import scipy as sp
import scipy.stats
import pandas as pd

from numpy import log, log10, sum, pi
from numpy.random import permutation
from scipy.special import gammaln


############################
#
# MODEL DEFINITION
#

logfactorial = lambda n: sum(log(np.arange(1, n + 1)))


class FitnessNetwork(object):
    """Base class for doing Gibbs sampling using the fitness Bayes network"""

    def __init__(self, Z, X, alpha=1.):
        """Always requires input Z and output X"""
        self.Z = Z
        self.X = X
        self.alpha = alpha
        self.N = len(X)
        self.n = sum(X)

    def sample_prior(self):
        raise NotImplementedError

    def sample_theta_given_w(self):
        raise NotImplementedError

    def sample_w_given_theta(self):
        raise NotImplementedError

    def loglikelihood_w(self, w):
        raise NotImplementedError

    def loglikelihood_theta(self, theta, w):
        raise NotImplementedError

    def loglikelihood_X(self, theta):
        raise NotImplementedError

    def loglikelihood(self, theta, w):
        return self.loglikelihood_w(w) + self.loglikelihood_theta(theta, w) + self.loglikelihood_X(theta)

    def generate_truth(self):
        w_truth = self.sample_prior()
        theta_truth = np.random.dirichlet(self.alpha * self.Z * w_truth)
        X_truth = np.random.multinomial(self.n, theta_truth)
        return(w_truth, theta_truth, X_truth)


class LogNormalFitnessNetwork(FitnessNetwork):

    def __init__(self, Z, X, mu=0., sigma=1.):
        FitnessNetwork.__init__(self, Z, X)
        self.mu = mu
        self.sigma = sigma

        # precompute a few constants for likelihoods
        self.a = -self.N * log(2 * pi * self.sigma ** 2) / 2
        self.b = logfactorial(self.n)
        self.c = sum([logfactorial(x) for x in self.X])

    def sample_prior(self):
        return np.random.lognormal(self.mu, self.sigma, self.N)

    def sample_theta_given_w(self, w):
        return np.random.dirichlet(self.alpha * self.Z * w + self.X)

    def sample_w_given_theta(self, w, theta):
        # changes w in place
        # returns fraction of accepted moves

        # precompute random variates
        r = np.random.normal(0, 0.1, self.N)
        w_star = w * np.exp(r)
        accept = log(np.random.rand(self.N))  # log of uniform variates for acceptance

        # metropolis-hastings
        num_accepted = 0
        for i in permutation(self.N):
            sum_aZw_not_i = sum(self.alpha * self.Z * w) - self.alpha * self.Z[i] * w[i]
            log_ratio = log(w[i]) - log(w_star[i]) - \
                        ((log(w_star[i]) - self.mu) ** 2 + (log(w[i]) - self.mu) ** 2) / (2 * self.sigma ** 2) + \
                        (w_star[i] - w[i]) * self.alpha * self.Z[i] * log(theta[i]) + \
                         gammaln(sum_aZw_not_i + self.alpha * self.Z[i] * w_star[i]) - gammaln(self.alpha * self.Z[i] * w_star[i]) - \
                        (gammaln(sum_aZw_not_i + self.alpha * self.Z[i] * w[i]     ) - gammaln(self.alpha * self.Z[i] * w[i]    ))

            if accept[i] < log_ratio + r[i]:    # note: the 2nd term is a Jacobian
                w[i] = w_star[i]
                num_accepted += 1

        return float(num_accepted) / self.N

    def loglikelihood_w(self, w):
        return self.a - sum(log(w)) - sum((log(w) - self.mu) ** 2) / (2 * self.sigma ** 2)

    def loglikelihood_theta(self, theta, w):
        return sum((self.alpha * self.Z * w - 1) * log(theta)) + gammaln(sum(self.alpha * self.Z * w)) - sum(gammaln(self.alpha * self.Z * w))

    def loglikelihood_X(self, theta):
        return self.b - self.c + sum(self.X * log(theta))


class ParetoFitnessNetwork(FitnessNetwork):

    def __init__(self, Z, X, t=1.5):
        FitnessNetwork.__init__(self, Z, X)
        self.t = t

        # precompute a few constants for likelihoods
        self.a = self.N * log(self.t)
        self.b = logfactorial(self.n)
        self.c = sum([logfactorial(x) for x in self.X])

    def sample_prior(self):
        return np.random.pareto(self.t, self.N) + 1

    def sample_theta_given_w(self, w):
        return np.random.dirichlet(self.alpha * self.Z * w + self.X)

    def sample_w_given_theta(self, w, theta):
        # changes w in place
        # returns fraction of accepted moves

        # precompute random variates
        r = np.random.normal(0, 0.1, self.N)
        w_star = w * np.exp(r)
        accept = log(np.random.rand(self.N))  # log of uniform variates for acceptance

        # metropolis-hastings
        num_accepted = 0
        for i in permutation(self.N):
            sum_aZw_not_i = sum(self.alpha * self.Z * w) - self.alpha * self.Z[i] * w[i]
            log_ratio = (self.t + 1) * (log(w[i]) - log(w_star[i])) + \
                        (w_star[i] - w[i]) * self.alpha * self.Z[i] * log(theta[i]) + \
                        gammaln(self.alpha * self.Z[i] * w[i]) - gammaln(self.alpha * self.Z[i] * w_star[i]) + \
                        gammaln(self.alpha * self.Z[i] * w_star[i] + sum_aZw_not_i) - gammaln(self.alpha * self.Z[i] * w[i] + sum_aZw_not_i)

            if accept[i] < log_ratio + r[i]:    # note: the 2nd term is a Jacobian
                w[i] = w_star[i]
                num_accepted += 1

        return float(num_accepted) / self.N

    def loglikelihood_w(self, w):
        return self.a - (self.t + 1) * sum(log(w))

    def loglikelihood_theta(self, theta, w):
        return sum((self.alpha * self.Z * w - 1) * log(theta)) + gammaln(sum(self.alpha * self.Z * w)) - sum(gammaln(self.alpha * self.Z * w))

    def loglikelihood_X(self, theta):
        return self.b - self.c + sum(self.X * log(theta))


class SymParetoFitnessNetwork(FitnessNetwork):

    def __init__(self, Z, X, t=1.5):
        FitnessNetwork.__init__(self, Z, X)
        self.t = t

        # precompute a few constants for likelihoods
        # self.a = self.N * log(self.t)
        # self.b = logfactorial(self.n)
        # self.c = sum([logfactorial(x) for x in self.X])

    def sample_prior(self):
        enrichment = np.random.pareto(self.t, self.N) + 1
        depletion = 1. / enrichment
        choices = sp.stats.bernoulli.rvs(0.5,size=self.N)
        return np.choose(choices,[enrichment,depletion])



class GammaFitnessNetwork(FitnessNetwork):

    def __init__(self, Z, X, scale=1., shape=1.):
        FitnessNetwork.__init__(self, Z, X)
        self.scale = scale
        self.shape = shape

        # precompute a few constants for likelihoods
        self.a = -self.shape * self.N * log(self.scale) - self.N * gammaln(self.shape)
        self.b = logfactorial(self.n)
        self.c = sum([logfactorial(x) for x in self.X])

    def sample_prior(self):
        return np.random.gamma(self.shape, self.scale, self.N)

    def sample_theta_given_w(self, w):
        return np.random.dirichlet(self.alpha * self.Z * w + self.X)

    def sample_w_given_theta(self, w, theta):
        # changes w in place
        # returns fraction of accepted moves

        # precompute random variates
        r = np.random.normal(0, 0.1, self.N)
        w_star = w * np.exp(r)
        accept = log(np.random.rand(self.N))  # log of uniform variates for acceptance

        # metropolis-hastings
        num_accepted = 0
        for i in permutation(self.N):
            sum_aZw_not_i = sum(self.alpha * self.Z * w) - self.alpha * self.Z[i] * w[i]
            log_ratio = (self.shape - 1) * (log(w[i]) - log(w_star[i])) - \
                        (w_star[i] - w[i]) / self.scale + \
                        (w_star[i] - w[i]) * self.alpha * self.Z[i] * log(theta[i]) + \
                         gammaln(sum_aZw_not_i + self.alpha * self.Z[i] * w_star[i]) - gammaln(self.alpha * self.Z[i] * w_star[i]) - \
                        (gammaln(sum_aZw_not_i + self.alpha * self.Z[i] * w[i]     ) - gammaln(self.alpha * self.Z[i] * w[i]    ))

            if accept[i] < log_ratio + r[i]:    # note: the 2nd term is a Jacobian
                w[i] = w_star[i]
                num_accepted += 1

        return float(num_accepted) / self.N

    def loglikelihood_w(self, w):
        return self.a + (self.shape - 1) * sum(log(w)) - sum(w) / self.scale

    def loglikelihood_theta(self, theta, w):
        return sum((self.alpha * self.Z * w - 1) * log(theta)) + gammaln(sum(self.alpha * self.Z * w)) - sum(gammaln(self.alpha * self.Z * w))

    def loglikelihood_X(self, theta):
        return self.b - self.c + sum(self.X * log(theta))


############################
#
# PLOTS
#

centered = lambda x: np.exp(np.log(x) - np.mean(np.log(x)))
centered_matrix = lambda x: np.exp(np.log(x) - np.mean(np.log(x), axis=1).reshape((x.shape[0], 1)))

show = lambda fig, output_dir, output_file: fig.show() if output_dir == None else fig.savefig(os.path.join(output_dir, output_file))


class GibbsSamplingAnalysis(object):
    """Provide many plots from the output of Gibbs sampling"""
    def __init__(self, Z, X, alpha, iterations, ws, thetas, llws, llths, llXs, lls, frac_accepted):
        self.Z = Z
        self.X = X
        self.ratios = np.float_(self.X) / self.Z
        self.alpha = alpha
        self.iterations = iterations
        self.N = len(X)
        self.n = sum(X)
        self.ws = np.asarray(ws)
        self.thetas = np.asarray(thetas)
        self.llws = llws
        self.llths = llths
        self.llXs = llXs
        self.lls = lls
        self.log10_w_sums = [sum(log10(w_current)) for w_current in self.ws]
        self.frac_accepted = frac_accepted
        self.stds = np.std(log10(self.ws[-1000:, :]), axis=0)
        self.medians = np.median(self.ws[-1000:, :], axis=0)
        self.means = np.mean(self.ws[-1000:, :],  axis=0)
        self.extreme_log10_w = max(np.abs(np.min(log10(self.ws))), np.abs(np.max(log10(self.ws))))
        self.log10modes = [h[1][np.argmax(h[0])] for h in (np.histogram(log10(w_component), bins=100, range=(-self.extreme_log10_w, self.extreme_log10_w)) for w_component in self.ws[-1000:, :].T)]
        self.order_by_ws_last = np.argsort(self.ws[-1, :])[::-1]
        self.order_by_median_ws = np.argsort(self.medians)[::-1]
        self.order_by_input = np.argsort(self.Z)
        self.diffs_log10ws = np.diff(log10(self.ws.T))
        self.extreme_diff = max(np.abs(np.min(self.diffs_log10ws)), np.abs(np.max(self.diffs_log10ws)))
        self.updates = np.sum(self.diffs_log10ws != 0, axis=1)
        self.dirichlet_weights = np.sum(self.ws * Z * alpha, axis=1)
        self.percentiles_at_1 = [sp.stats.percentileofscore(self.ws[-500:, i], 1) for i in range(self.N)]
        self.p5  = sp.stats.scoreatpercentile(log10(centered_matrix(self.ws)), 5)
        self.p25 = sp.stats.scoreatpercentile(log10(centered_matrix(self.ws)), 25)
        self.p50 = sp.stats.scoreatpercentile(log10(centered_matrix(self.ws)), 50)
        self.p75 = sp.stats.scoreatpercentile(log10(centered_matrix(self.ws)), 75)
        self.p95 = sp.stats.scoreatpercentile(log10(centered_matrix(self.ws)), 95)
        self.iter_norm = mpl.colors.normalize(0, len(self.ws) - 1)

    def loglikelihoods(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(self.llws, label='w')
        ax.plot(self.llths, label='theta')
        ax.plot(self.llXs, label='X')
        ax.plot(self.lls, label='combined')
        ax.set_xlabel('iteration')
        ax.set_title('log likelihoods')
        ax.legend(loc=4)
        show(fig, output_dir, 'loglikelihoods.png')

    def frac_accepted_plot(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(self.frac_accepted)
        ax.set_xlabel('iteration')
        ax.set_ylabel('frac moves accepted')
        show(fig, output_dir, 'frac_accepted_plot.png')

    def ranked_ws(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for (i, w_current) in enumerate(self.ws):
            if i % 200 == 0:
                ax.plot(range(1, len(w_current) + 1), sorted(log10(centered(w_current)), reverse=True), color=mpl.cm.jet(self.iter_norm(i)), clip_on=False)
        ax.set_xlabel('rank (big to small)')
        ax.set_ylabel('log10(w)')
        show(fig, output_dir, 'ranked_ws.png')

    def w_distributions_ordered_by_medians(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(range(self.N), self.p5[self.order_by_median_ws],  s=5, c='k', lw=0, zorder=1)
        ax.scatter(range(self.N), self.p95[self.order_by_median_ws], s=5, c='k', lw=0, zorder=1)
        for (pos, low, high) in zip(range(self.N), self.p25[self.order_by_median_ws], self.p75[self.order_by_median_ws]):
            ax.plot([pos, pos], [low, high], color='#bdbdbd', lw=2, zorder=2)
        ax.scatter(range(self.N), self.p50[self.order_by_median_ws], s=10, c='r', linewidths=0, zorder=3)
        ax.axhline(0, zorder=0)
        ax.set_xlabel('w component (big to small)')
        ax.set_ylabel('w value')
        show(fig, output_dir, 'w_distributions_ordered_by_medians.png')

    def w_distributions_ordered_by_input(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(range(self.N), self.p5[self.order_by_input],  s=5, c='k', lw=0, zorder=1)
        ax.scatter(range(self.N), self.p95[self.order_by_input], s=5, c='k', lw=0, zorder=1)
        for (pos, low, high) in zip(range(self.N), self.p25[self.order_by_input], self.p75[self.order_by_input]):
            ax.plot([pos, pos], [low, high], color='#bdbdbd', lw=2, zorder=2)
        ax.scatter(range(self.N), self.p50[self.order_by_input], s=10, c='r', linewidths=0, zorder=3)
        ax.axhline(0, zorder=0)
        ax.set_xlabel('w component (small to big)')
        ax.set_ylabel('w value')
        show(fig, output_dir, 'w_distributions_ordered_by_input.png')

    def ranked_stds(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(sorted(self.stds))
        ax.set_xlabel('rank')
        ax.set_ylabel('std of each component in last 1000 w vectors')
        show(fig, output_dir, 'ranked_stds.png')

    def dirichlet_weights_trajectory(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(range(self.iterations + 1), self.dirichlet_weights)
        ax.set_xlabel('iteration')
        ax.set_ylabel('Z * w')
        show(fig, output_dir, 'dirichlet_weights_trajectory.png')

    def evolution_w_hist(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for (i, w_current) in enumerate(self.ws):
            if i % 200 == 0:
                ax.hist(log10(w_current), bins=100, log=True, histtype='step', color=mpl.cm.jet(self.iter_norm(i)), linewidth=1, alpha=0.5)
        ax.set_xlabel('log10(w)')
        show(fig, output_dir, 'evolution_w_hist.png')

    def total_w_weight(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(self.log10_w_sums)
        ax.set_xlabel('iteration')
        ax.set_ylabel('sum(log10(w))')
        show(fig, output_dir, 'total_w_weight.png')

    def raw_data_by_w(self, output_dir=None):
        # plot ip/op data colored by estimated w value or variance in estimate
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(self.Z, self.X, c=log10(self.medians), cmap=mpl.cm.RdBu, vmin=-self.extreme_log10_w, vmax=self.extreme_log10_w, s=25, lw=0.5, clip_on=False, zorder=10)
        ax.set_yscale('log')
        ax.set_xlabel('input count')
        ax.set_ylabel('output count')
        ax.axis([0, 1200, 1, 1e3])
        bar = fig.colorbar(ax.collections[0])
        bar.set_label('log10(w)')
        show(fig, output_dir, 'raw_data_by_w.png')

    def raw_data_by_std(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(self.Z, self.X, c=-self.stds, cmap=plt.jet(), s=25, lw=0.5, clip_on=False, zorder=10)
        ax.set_yscale('log')
        ax.set_xlabel('input count')
        ax.set_ylabel('output count')
        ax.axis([0, 1200, 1, 1e3])
        bar = fig.colorbar(ax.collections[0])
        bar.set_label('-1*std(w)')
        show(fig, output_dir, 'raw_data_std.png')

    def trajectories(self, output_dir=None):
        segments = tuple([np.c_[np.arange(self.iterations + 1), log10(trajectory)] for trajectory in self.ws.T])
        coll = mpl.collections.LineCollection(segments, colors=(0, 0, 0, 0.1))
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.set_xlim([0, self.iterations])
        ax.set_ylim([np.min(log10(self.ws)) * 0.9, np.max(log10(self.ws)) * 1.1])
        ax.add_collection(coll)
        ax.set_xlabel('iteration')
        ax.set_ylabel('w component')
        show(fig, output_dir, 'trajectories.png')

    def trajectories_heatmap(self, output_dir=None):
        fig = plt.figure(figsize=((self.iterations + 1) / 250., self.N / 250.))
        ax = fig.add_axes([0.1, 0.1, 0.87, 0.87])
        ax.imshow(log10(self.ws.T)[self.order_by_ws_last, :], aspect='auto', interpolation='nearest', cmap=mpl.cm.RdBu, vmin=-self.extreme_log10_w, vmax=self.extreme_log10_w)
        ax.set_xlabel('iteration')
        ax.set_ylabel('w component')
        show(fig, output_dir, 'trajectories_heatmap.png')

    def trajectory_derivatives_spy(self, output_dir=None):
        fig = plt.figure(figsize=((self.iterations + 1) / 250., self.N / 250.))
        ax = fig.add_axes([0.1, 0.1, 0.87, 0.87])
        ax.spy(self.diffs_log10ws[self.order_by_ws_last, :], aspect='auto')
        ax.set_xlabel('iteration')
        ax.set_ylabel('w component')
        show(fig, output_dir, 'trajectory_derivatives_spy.png')

    def hist_num_updates(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.hist(self.updates, bins=50)
        ax.set_xlabel('num updates for a given w in %i iterations' % self.iterations)
        show(fig, output_dir, 'hist_num_updates.png')

    def num_updates_vs_median_w(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(np.abs(log10(self.medians)), self.updates)
        ax.set_xlabel('log10(median w value)')
        ax.set_ylabel('num updates for that values in %i iterations' % self.iterations)
        show(fig, output_dir, 'num_updates_vs_median_w.png')

    def num_updates_vs_std_w(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(np.abs(self.stds), self.updates)
        ax.set_xlabel('std(w)')
        ax.set_ylabel('num updates for that values in %i iterations' % self.iterations)
        show(fig, output_dir, 'num_updates_vs_std_w.png')

    def median_w_vs_std_w(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(log10(self.medians), self.stds)
        ax.set_xlabel('log10(median w)')
        ax.set_ylabel('std(w)')
        show(fig, output_dir, 'median_w_vs_std_w.png')

    def simulated_data(self, output_dir=None):
        theta_sim = np.random.dirichlet(self.alpha * self.Z * self.medians)
        X_sim = np.random.multinomial(self.n, theta_sim)
        fig = plt.figure()

        ax = fig.add_subplot(211)
        ax.scatter(self.Z, self.X, c='k', s=3, lw=0)
        ax.set_yscale('log')
        ax.axis([0, 2000, 1, 1e3])
        ax.set_ylabel('real data')

        ax = fig.add_subplot(212)
        ax.scatter(self.Z, X_sim, c='k', s=3, lw=0)
        ax.set_yscale('log')
        ax.axis([0, 2000, 1, 1e3])
        ax.set_ylabel('simulated')

        show(fig, output_dir, 'generated_data.png')


class GibbsSamplingAnalysis_with_truth(GibbsSamplingAnalysis):
    """Provide many plots from the output of Gibbs sampling"""
    def __init__(self, w_truth, theta_truth, Z, X, alpha, iterations, ws, thetas, llws, llths, llXs, lls, frac_accepted):
        GibbsSamplingAnalysis.__init__(self, Z, X, alpha, iterations, ws, thetas, llws, llths, llXs, lls, frac_accepted)
        self.w_truth = w_truth
        self.theta_truth = theta_truth
        self.theta_err_L1 = np.sum(np.abs(self.thetas - self.theta_truth), axis=1)
        self.theta_err_L2 = np.sqrt(np.sum((self.thetas - self.theta_truth) ** 2, axis=1))

    def ranked_ws(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for (i, w_current) in enumerate(self.ws):
            if i % 200 == 0:
                ax.plot(range(1, len(w_current) + 1), sorted(log10(centered(w_current)), reverse=True), color=mpl.cm.jet(self.iter_norm(i)), clip_on=False)
        ax.plot(range(1, len(self.w_truth) + 1), sorted(log10(centered(self.w_truth)), reverse=True), '-k', clip_on=False, linewidth=2)
        ax.set_xlabel('rank (big to small)')
        ax.set_ylabel('log10(w)')
        show(fig, output_dir, 'ranked_ws.png')

    def w_truth_vs_median_w(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(log10(centered(self.medians)), log10(centered(self.w_truth)), c=self.stds, cmap=plt.jet(), s=25, clip_on=False, lw=0.5)
        ax.set_xlabel('log10(median w)')
        ax.set_ylabel('log10(true w)')
        ax.axis([np.min(np.log10([self.w_truth, self.medians])), np.max(np.log10([self.w_truth, self.medians])), np.min(np.log10([self.w_truth, self.medians])), np.max(np.log10([self.w_truth, self.medians]))])
        show(fig, output_dir, 'w_truth_vs_median_w.png')
    
    def w_truth_vs_median_w_by_ratio(self, output_dir=None):
        idxs_finite = np.isfinite(log10(self.ratios))
        minlog10ratio = np.min(log10(self.ratios[idxs_finite]))
        maxlog10ratio = np.max(log10(self.ratios[idxs_finite]))
        extremelog10ratio = np.max(np.abs([minlog10ratio,maxlog10ratio]))
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(log10(centered(self.medians)), log10(centered(self.w_truth)), c=log10(self.ratios), cmap=mpl.cm.RdBu, vmin=-extremelog10ratio, vmax=extremelog10ratio, s=25, clip_on=False, lw=0.5)
        ax.set_xlabel('log10(median w)')
        ax.set_ylabel('log10(true w)')
        ax.axis([np.min(np.log10([self.w_truth, self.medians])), np.max(np.log10([self.w_truth, self.medians])), np.min(np.log10([self.w_truth, self.medians])), np.max(np.log10([self.w_truth, self.medians]))])
        bar = fig.colorbar(ax.collections[0])
        bar.set_label('log10(output/input)')
        show(fig, output_dir, 'w_truth_vs_median_w_by_ratio.png')
    
    def w_truth_vs_mean_w(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(log10(centered(self.means)), log10(centered(self.w_truth)), c=self.stds, cmap=plt.jet(), s=25, clip_on=False, lw=0.5)
        ax.set_xlabel('log10(mean w)')
        ax.set_ylabel('log10(true w)')
        ax.axis([np.min(np.log10([self.w_truth, self.means])), np.max(np.log10([self.w_truth, self.means])), np.min(np.log10([self.w_truth, self.means])), np.max(np.log10([self.w_truth, self.means]))])
        show(fig, output_dir, 'w_truth_vs_mean_w.png')

    def w_truth_vs_median_w_ranks(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(sp.stats.rankdata(centered(self.medians)), sp.stats.rankdata(centered(self.w_truth)), c=self.stds, cmap=plt.jet(), s=25, clip_on=False, lw=0.5)
        ax.set_xlabel('rank median w')
        ax.set_ylabel('rank true w')
        show(fig, output_dir, 'w_truth_vs_median_w_ranks.png')

    def raw_data_by_true_w(self, output_dir=None):
        extreme_log10_centered_w_truth = max(np.abs(np.min(log10(centered(self.w_truth)))), np.abs(np.max(log10(centered(self.w_truth)))))
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(self.Z, self.X, c=log10(centered(self.w_truth)), cmap=mpl.cm.RdBu, vmin=-extreme_log10_centered_w_truth, vmax=extreme_log10_centered_w_truth, s=25, lw=0.5, clip_on=False, zorder=10)
        ax.set_yscale('log')
        ax.set_xlabel('input count')
        ax.set_ylabel('output count')
        ax.axis([0, 1200, 1, 1e3])
        bar = fig.colorbar(ax.collections[0])
        bar.set_label('log10(centered(w_truth))')
        show(fig, output_dir, 'raw_data_by_true_w.png')
    
    def error_vs_updates(self, output_dir=None):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(log10(centered(self.w_truth)) - log10(centered(self.medians)), self.updates, c=self.stds, cmap=plt.jet(), s=25, clip_on=False, lw=0.5)
        ax.set_xlabel('log10(w_truth)-log10(median w)')
        ax.set_ylabel('num updates')
        show(fig, output_dir, 'error_vs_updates.png')



############################
#
# MAIN SCRIPT
#

if __name__ == '__main__':

    import argparse

    argparser = argparse.ArgumentParser(description=None)
    argparser.add_argument('--input')
    argparser.add_argument('--output', default='output.csv')
    argparser.add_argument('--prior', default='lognormal')
    argparser.add_argument('--iterations', type=int, default=3000)
    argparser.add_argument('--subsample', type=int, default=0)
    argparser.add_argument('--truth', action='store_true')
    argparser.add_argument('--verbose', action='store_true')
    args = argparser.parse_args()

    def msg(txt):
        sys.stderr.write(txt)
        sys.stderr.flush()

    # check if I will dump out tons of figures about the process
    if args.verbose:
        output_dir = os.path.splitext(args.output)[0]
        os.makedirs(output_dir, mode=0755)
        output_file = os.path.basename(args.output)
    else:
        output_dir = os.getcwd()
        output_file = args.output

    # load data
    msg("Loading data...")
    full_df = pd.read_csv(args.input, index_col=None)
    full_df.columns = pd.Index(['clone', 'input', 'output'])
    msg("finished\n")

    # subsample rows to make problem smaller
    if args.subsample > 0:
        random_idxs = random.sample(xrange(full_df.shape[0]), args.subsample)
        df = full_df.ix[random_idxs]
    else:
        df = full_df

    Z = np.array(df['input']) + 1   # add pseudocount
    X = np.array(df['output'])

    # define the model
    msg("Defining model...")
    if args.prior == 'lognormal':
        model = LogNormalFitnessNetwork(Z=Z, X=X, mu=0., sigma=2)
        if args.truth:
            (w_truth, theta_truth, X) = model.generate_truth()
            model = LogNormalFitnessNetwork(Z=Z, X=X, mu=0., sigma=1.)
    elif args.prior == 'pareto':
        model = ParetoFitnessNetwork(Z=Z, X=X, t=1.5)
        if args.truth:
            (w_truth, theta_truth, X) = model.generate_truth()
            model = ParetoFitnessNetwork(Z=Z, X=X, t=1.5)
    elif args.prior == 'gamma':
        model = GammaFitnessNetwork(Z=Z, X=X, scale=1., shape=1.)
        if args.truth:
            (w_truth, theta_truth, X) = model.generate_truth()
            model = GammaFitnessNetwork(Z=Z, X=X, scale=1., shape=1.)
    else:
        raise ValueError("Unrecognized prior")
    msg("finished\n")

    # SAMPLING
    msg("Starting Gibbs sampler...\n")

    # sample from prior on w
    w = model.sample_prior()

    # variables to store intermediate values
    ws = [w]
    thetas = []
    llws = []   # log likelihood of ws give current values
    llths = []  # log likelihood of thetas given current values
    llXs = []   # log likelihood of Xs given current values
    lls = []    # total log likelihood
    frac_accepted = []  # fraction of moves accepted

    # main loop for Gibbs sampling
    for i in xrange(args.iterations):
        if i % 10 == 0:
            sys.stderr.write("%i " % i)
            sys.stderr.flush()

        # sample from conditional over theta
        theta = model.sample_theta_given_w(w)

        # sample from conditional on fitness w
        # modifies w in place
        frac_accepted.append(model.sample_w_given_theta(w, theta))

        # save intermediate values
        ws.append(w.copy())
        thetas.append(theta.copy())

        # compute log likelihoods
        llws.append(model.loglikelihood_w(w))
        llths.append(model.loglikelihood_theta(theta, w))
        llXs.append(model.loglikelihood_X(theta))
        lls.append(llws[-1] + llths[-1] + llXs[-1])

    msg("\n...finished\n")

    ws = np.asarray(ws)
    median_w = np.median(ws[-1000:, :],  axis=0)
    mean_w = np.mean(ws[-1000:, :],  axis=0)
    std_w = np.std(ws[-1000:, :], axis=0)
    p5_w  = sp.stats.scoreatpercentile(log10(centered_matrix(ws)), 5)
    p95_w = sp.stats.scoreatpercentile(log10(centered_matrix(ws)), 95)

    # write results to disk
    msg("Writing w values to disk...")
    df['w'] = median_w
    df['std_w'] = std_w
    df['p5_w'] = p5_w
    df['p95_w'] = p95_w
    df.to_csv(os.path.join(output_dir, output_file), index=False, cols=['clone', 'w', 'p5_w', 'p95_w', 'std_w'])
    msg("finished\n")

    # GENERATE FIGURES (verbose output)
    if args.verbose:
        msg("Computing values for figures...")
        if not args.truth:
            plots = GibbsSamplingAnalysis(Z, X, model.alpha, args.iterations, ws, thetas, llws, llths, llXs, lls, frac_accepted)
        else:
            plots = GibbsSamplingAnalysis_with_truth(w_truth, theta_truth, Z, X, model.alpha, args.iterations, ws, thetas, llws, llths, llXs, lls, frac_accepted)
        msg("finished\n")

        msg("Plotting figures...")
        plots.loglikelihoods(output_dir)
        plots.frac_accepted_plot(output_dir)
        plots.ranked_ws(output_dir)
        plots.w_distributions_ordered_by_medians(output_dir)
        plots.w_distributions_ordered_by_input(output_dir)
        plots.ranked_stds(output_dir)
        plots.dirichlet_weights_trajectory(output_dir)
        plots.evolution_w_hist(output_dir)
        plots.total_w_weight(output_dir)
        plots.raw_data_by_w(output_dir)
        plots.raw_data_by_std(output_dir)
        plots.trajectories(output_dir)
        plots.trajectories_heatmap(output_dir)
        plots.trajectory_derivatives_spy(output_dir)
        plots.hist_num_updates(output_dir)
        plots.num_updates_vs_median_w(output_dir)
        plots.num_updates_vs_std_w(output_dir)
        plots.median_w_vs_std_w(output_dir)
        plots.simulated_data(output_dir)

        if args.truth:
            plots.w_truth_vs_median_w(output_dir)
            plots.w_truth_vs_median_w_ranks(output_dir)
            plots.raw_data_by_true_w(output_dir)

        msg("finished\n")
