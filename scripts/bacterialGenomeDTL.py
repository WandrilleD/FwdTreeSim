#!/usr/bin/python

import sys, os, copy
#~ import argparse
import getopt
from FwdTreeSim import models, simulators, IOsimul
import tree2
import random

def usage():
	crindent = "\t\t\t\t\t"
	l =  ["Usage:"]
	#~ l += ["python bacterialGenomeDTL.py [options]"]
	l += ["python %s [options]"%(sys.argv[0])]
	l += ["Options:"]
	l += ["  General options:"]
	l += ["\t-o  --outputdir path\t\tdirectory for all output files #\tdefaults to current directory."]
	
	l += ["  Simulation parameters:"]
	l += ["  __Species/Genomes population layer__:"]
	l += ["\t-s  --popsize   int\t\tnumber of species to simulate in the underlying Moran process\t# default: 100."]
	l += ["\t-g  --ngen      int\t\tnumber of generation for which the evolution is simulated\t# default: 1000."]
	
	l += ["  __Gene/Locus layer__:"]
	l += ["\t-p  --profiles  path\t\tJSON file containing the (multiple) evolutionary profiles for simulated gene families, ", \
	      crindent+"and their respective weights (sampling probability if <=1 or expected number of gene families if >1).", \
	      crindent+"See FwdTreeSim/example/DTLprofiles.json for file format example.", \
	      crindent+"Example pangenome structure (with 20% core, 20% accessory, 60% orfan gene families)", \
	      crindent+"can be generated by replacing path by an empty string ''. "]
	l += ["\t-n  --ngenes    int\t\tnumber of gene families to simulate in the pangenome\t# default: 10; overriden by providing gene family profiles."]
	l += ["\t-r  --dtlrates  float[,float[,float]]\tglobal rates of Duplication, Transfer and Loss for ALL simulated gene families.", \
	      crindent+"# default: D=0.001 T=D, L=D+T; overriden by providing gene family profiles."]
	l += ["\t-f  --rootfreq  float\t\tglobal presence probability for ALL the gene families at the root of the simulation of the species population.", \
	      crindent+"# default: 0.5 ; overriden by providing gene family profiles."]
	
	l += ["  Output options:"]
	l += ["\t-e  --sample.extant.species int\t\thow many genomes are sampled in the end? trees are pruned accordingly\t# all sampled by default."]
	l += ["\t-l  --sample.larger.trees int\thow many single gene trees from a gene family population should be written out?", \
	      crindent+"Can be handy to just diagnostic the simulated trees # all written by default."]
	l += ["\t-c  --connect.all.trees float\tIn addition, return the multiple gene trees from a gene family population as one, connecting them at their root.", \
	      crindent+"Length of branches of the star root is given by the argument, negative value turns it off # default: 0 (on)."]
	return '\n'.join(l)

def main():
	
	# option parsing
	try:
		opts, args = getopt.getopt(sys.argv[1:], "o:n:r:f:e:l:c:p:vh", ["outputdir=", "ngenes=", "popsize=", "ngen=", \
																	"dtlrates=", "rootfreq=", "profiles=", \
																	"sample.larger.trees=", "connect.all.trees=", "sample.extant.species=", \
																	"help", "verbose"])
	except getopt.GetoptError as err:
		# print help information and exit:
		print str(err)  # will print something like "option -a not recognized"
		print usage()
		sys.exit(2)
		
	dopt = dict(opts)
	if ('-h' in dopt) or ('--help' in dopt):
		print usage()
		sys.exit(0)
	if ('-v' in dopt) or ('--verbose' in dopt): silent = False
	else: silent = True
	outdir = dopt.get('-o', dopt.get('--outputdir', os.getcwd()))
	popsize = int(dopt.get('-s', dopt.get('--popsize', 100)))
	ngen = int(dopt.get('-g', dopt.get('--ngen', 1000)))

	nfprofiles = dopt.get('-p', dopt.get('--profiles'))
	# define the evolution rates and original frequencies of gene families
	if nfprofiles!=None:
		if nfprofiles=='':
			exsampleprof = [(2, 'core'), (2, 'accessory-slow'), (6, 'orfan-fast')]
			dtlprof = IOsimul.MetaSimulProfile(profiles=[(n, IOsimul.DTLSimulProfile(type=t)) for n,t in exsampleprof])
		else:
			# expects a JSON formating of simulator profiles conforming to the IOsimul.MetaSimulProfile class parsers
			# e.g. a list of dict objects representing the arguments of a simulators.DTLSimulProfile class instance
			dtlprof = IOsimul.MetaSimulProfile(json=nfprofiles)
	else:
		# default global parameters (no pangenome structure), overridden by any provided profile
		rootfreq = dopt.get('-f', dopt.get('--rootfreq', 0.5))
		sdtlrates = dopt.get('-r', dopt['--dtlrates'])
		if sdtlrates:
			dtlrates = [float(s) for s in dopt.get('-r', dopt['--dtlrates']).split(',')]
		else:                                           # by default, rates are:
			dtlrates = [0.001] 							# D = 1e-3
		if len(dtlrates)<2: dtlrates += dtlrates[0]		# T = D
		if len(dtlrates)<3: dtlrates += [sum(dtlrates)] # L = T+D
		dglobalprof = {0:{'rdup':dtlrates[0], 'rtrans':dtlrates[1], 'rloss':dtlrates[2]}}
		globalprof = IOsimul.DTLSimulProfile(rateschedule=dglobalprof, rootfreq=rootfreq)
		dtlprof = IOsimul.MetaSimulProfile(profiles=[(1, globalprof)])

	# derive number of gene families to simulate from profile weights, or from dedicated option -n (overrides profiles), or take default value of 10
	if dtlprof.ngenes>1:
		ngenes = dtlprof.ngenes
	else:
		ngenes = int(dopt.get('-n', dopt.get('--ngenes', 10)))

	nlargegenetrees = int(dopt.get('-l', dopt.get('--sample.larger.trees', -1)))
	lentoroot = float(dopt.get('-c', dopt.get('--connect.all.trees', -1)))
	samplextant = int(dopt.get('-e', dopt.get('--sample.extant.species', 0)))
	assert samplextant <= popsize

	#~ parser = argparse.ArgumentParser(description='Simulate phylogenic trees describing evolution of a population of bacterial genomes, with species, replicon/locus and gene layers.')
	#~ parser.add_argument('-o', '--outdir', )

	# creating output directories
	for d in ['logs', 'pickles', 'genetrees', 'reftrees']:
		outd = "%s/%s"%(outdir, d)
		if not os.path.exists(outd):
			os.mkdir(outd)

	# simualte species tree
	moranmodel = models.MoranProcess(popsize=popsize)
	moransim = simulators.MultipleTreeSimulator(moranmodel, ngen=ngen)
	if lentoroot>=0:
		# connect all roots of the species lineage trees
		conrt = moransim.connecttrees(lentoroot, returnCopy=True)
		conrt.write_newick("%s/reftrees/connected.reftree_full.nwk"%(outdir))
		# prune dead lineages and connect all roots of the species lineage trees
		extconrt = moransim.get_extanttree(compute=True, lentoroot=lentoroot)
		extconrt.write_newick("%s/reftrees/connected.reftree_extant.nwk"%(outdir))
		extantspe = extconrt.get_leaf_labels()
	else:
		# write lineage trees separately
		lextrt = moransim.get_extanttrees(compute=True)
		extantspe = []
		for k, extrt in enumerate(lextrt):
			extconrt.write_newick("%s/reftrees/reftree.%d_extant.nwk"%(outdir, k))
			extantspe += extconrt.get_leaf_labels()
			
	# select sampled species among the N extant
	if samplextant:
		sampledspe = random.sample(extantspe, samplextant)
		refnodeswithdescent = moransim.get_nodes_with_descendants(sample=sampledspe)
	else:
		refnodeswithdescent = moransim.get_nodes_with_descendants()
	# serial simulation of gene families, have to offer a parrallel version
	for k in range(ngenes):
		print "### simulate gene tree", k
		# simulate gene tree under the same reference tree set (= species/organism population history)
		#~ bddtlmodel = models.BirthDeathDTLModel(rdup=dtlrates[0], rtrans=dtlrates[1], rloss=dtlrates[2])
		bddtlmodel = models.BirthDeathDTLModel()
		bddtlsim = simulators.DTLtreeSimulator(model=bddtlmodel, refsimul=moransim, refnodeswithdescent=refnodeswithdescent, profile=dtlprof.sampleprofile(verbose=True), noTrigger=True)
		bddtlsim.evolve(bddtlsim.ngen)

		# save ref and gene tree simulation object together to save space as they share references to same objects
		IOsimul.dumppickle({'refsim':moransim, 'genesim':bddtlsim}, "%s/pickles/simul.%d.pickle"%(outdir, k))

		# write out the largest n gene trees and corresponding species trees
		if nlargegenetrees>=0:
			genetreesizes = [(genetree.nb_leaves(), i) for i, genetree in enumerate(bddtlsim.genetrees)]
			genetreesizes.sort(reverse=True)
			isavetrees = (genetreesizes[l][1] for l in range(nlargegenetrees))
		else:
			isavetrees = xrange(len(bddtlsim.genetrees))
		for l in isavetrees:
			genetree = bddtlsim.genetrees[l]
			genetree.write_newick("%s/genetrees/simul.%d.all_gt.nwk"%(outdir, k), mode=('w' if l==0 else 'a'))
			#~ genetree.ref.write_newick("%s/reftrees/simul.%d.rt.%d.nwk"%(outdir, k, l))
		
		if lentoroot>=0:
			# connect all the gene trees in each gene population
			congt = bddtlsim.connecttrees(lentoroot, returnCopy=True)
			# write out connected trees
			congt.write_newick("%s/genetrees/simul.%d.connected_gt_full.nwk"%(outdir, k))
			# prune dead lineages and connect all roots of the species lineage trees
			extconrt = bddtlsim.get_extanttree(compute=True, lentoroot=lentoroot)
			print extconrt
			extconrt.write_newick("%s/genetrees/simul.%d.connected_gt_extant.nwk"%(outdir, k))
				
if __name__=='__main__':
	main()
