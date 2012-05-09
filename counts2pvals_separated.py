#! /usr/bin/env python

import os
import sys
import argparse
import glob
import subprocess

def submit_to_LSF(queue,LSFopfile,cmd_to_submit,mem_usage=None):
    # wrap command to submit in quotations
    cmd_to_submit = r'"%s"' % cmd_to_submit.strip(r'"')
    LSF_params = {'LSFoutput':LSFopfile,
                      'queue':queue}
    LSF_cmd = 'bsub -q%(queue)s -o%(LSFoutput)s' % LSF_params
    if mem_usage != None:
        LSF_cmd += r' -R "rusage[mem=%d]"' % mem_usage
    cmd = ' '.join([LSF_cmd,cmd_to_submit])
    p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE)
    #p.wait()
    return p.stdout.read().split('<')[1].split('>')[0]

def submit_to_SGE(queue,log_file,cmd_to_submit,mem_usage=None):
    # wrap command to submit in quotations
    cmd_to_submit = r'"%s"' % cmd_to_submit.strip(r'"')
    SGE_params = {'log_output':log_file,
                      'queue':queue}
    SGE_cmd = 'qsub -o %(log_output)s -b y -V -j y -cwd -q %(queue)s -N counts2pval' % SGE_params
    if mem_usage != None:
        SGE_cmd += r' -l h_vmem=%dG' % mem_usage
    cmd = ' '.join([SGE_cmd,cmd_to_submit])
    print cmd
    p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE)
    #p.wait()
    return p.stdout.read()

argparser = argparse.ArgumentParser(description=None)
argparser.add_argument('-i','--input',required=True)
argparser.add_argument('-o','--output',required=True)
argparser.add_argument('-q','--queue',required=True)
argparser.add_argument('-l','--logs',required=True)
argparser.add_argument('-m','--mem_usage',type=int,default=None)
args = argparser.parse_args()

input_dir = os.path.abspath(args.input)
output_dir = os.path.abspath(args.output)
os.makedirs(output_dir,mode=0755)
log_dir = os.path.abspath(args.logs)
os.makedirs(log_dir,mode=0755)

script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

for infilename in glob.glob(os.path.join(input_dir,'*.csv')):
    sample = '.'.join(os.path.basename(infilename).split('.')[:-1])
    outfilename = os.path.join(output_dir,'.'.join([sample,'pvals','csv']))
    logfilename = os.path.join(log_dir,'.'.join([sample,'pvals','log']))
    cmd = 'python %s/counts2pvals.py -i %s -o %s' % (script_dir,os.path.abspath(infilename),os.path.abspath(outfilename))
    print submit_to_SGE(args.queue,logfilename,cmd,mem_usage=args.mem_usage)
