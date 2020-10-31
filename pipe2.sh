#!/bin/bash

# first job - no dependencies, called from the day directory
# creates RPLParallel, Unity, and EDFSplit objects, and
# calls aligning_objects and raycast
jid1=$(sbatch /data/src/PyHipp/rplparallel-slurm.sh)

# second set of jobs - no dependencies, called from the day directory
jid2=$(sbatch /data/src/PyHipp/rs1-slurm.sh)
jid3=$(sbatch /data/src/PyHipp/rs2-slurm.sh)
jid4=$(sbatch /data/src/PyHipp/rs3-slurm.sh)
jid5=$(sbatch /data/src/PyHipp/rs4-slurm.sh)

# put dependency for any job that will spawn more jobs here
# sbatch --dependency=afterok:${jid1##* }:${jid2##* }:${jid3##* }:${jid4##* }:${jid5##* } /data/src/PyHipp/consol_jobs.sh

