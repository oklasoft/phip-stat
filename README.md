Pipeline for analyzing PhIP-seq data
------------------------------------

See [Larman et. al.][1] for more information.

The pipeline assumes that the initial data set is a single `.fastq` file with
all the reads, including a possible barcode in the header of each read.

First start by splitting the data into smaller chunks:

    fastq2parts.py -i in.fastq -o workdir/parts -p 2000000

Then align each read to the reference PhIP-seq library using `bowtie` (making
sure to set the right queue):

    bowtie_parts_with_LSF.py -i workdir/parts -o workdir/alns -x path/to/index_name.ebwt -l workdir/logs_aln -q short_serial

Then reads are reorganized according to barcode. The mapping file should be a
tab-separated file with the barcode sequence as the first column and the
sample name as the second column. The sample names should be something that's
friendly as a UNIX filename:

    parts2barcodes.py -i workdir/alns -o workdir/barcodes -m mapping.tsv

Now we must generate the counts and p-values.  There are two ways to proceed:

* Generate a single count file and a single p-value file, and have them all
  calculated at the same time.
* Perform counts and p-values on each sample
  separately. Each p-value calculation gets dispatched as a separate job.

For the single-file method:

    alns2counts.py -i workdir/barcodes -o workdir/counts.csv -r input_counts.csv
    counts2pvals.py -i workdir/counts.csv -o workdir/pvals.csv

For the parallel method (make sure to set the queue):

    alns2counts_separated.py -i workdir/barcodes -o workdir/counts -r input_counts.csv
    counts2pvals_separated.py -i workdir/counts -o workdir/pvals -q short_serial -l logs_pvals
    ls -l workdir/pvals/*.csv | awk '$5 == 0 {print $8}' | xargs rm -f  # remove empty pval files
    
    # NOTE: ensure that all empty files in workdir/pvals have been deleted
    merge_columns.py -f 2 -i workdir/pvals -o workdir/pvals.csv

Note that any of these commands can be dispatched to the LSF job scheduler.


PGM inference model
-------------------

There is a Gibbs sampling method for computing "selection values" as well.  This
script expects a CSV file with three columns: the clone names, the input counts,
and the output counts.

    gibbs.py --input counts.csv --output output.csv --verbose

The `--verbose` flag will instead create a directory called `output` and also
dump a bunch of diagnostic figures there.

There will soon be an `mcmc.py` script that will implement the more complex PGM
that allows multiple timepoints.


Other things to note
--------------------

If your CSV file is poluted with Windows-style line-endings, you can change that
with:

    tr '\r' '\n' < offending.csv > clean.csv

[1]: http://www.nature.com/nbt/journal/v29/n6/full/nbt.1856.html
